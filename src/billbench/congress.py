"""Congress.gov API v3 client with on-disk caching and CRS-summary/text-version matching."""
import hashlib
import json
import os
import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

BASE = "https://api.congress.gov/v3"
CACHE = Path("data/raw")

# CRS summary actionDesc -> text version types that reflect the same stage
_STAGE_ALIASES = {
    "introduced in house": ["introduced in house"],
    "introduced in senate": ["introduced in senate"],
    "reported to house": ["reported in house"],
    "reported to senate": ["reported in senate"],
    "passed house": ["engrossed in house", "received in senate"],
    "passed senate": ["engrossed in senate"],
    "public law": ["enrolled bill"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


class CongressClient:
    def __init__(self, api_key: str | None = None, pause: float = 0.25):
        self.key = api_key or os.environ["CONGRESS_API_KEY"]
        self.pause = pause
        self.http = httpx.Client(timeout=60, follow_redirects=True)
        CACHE.mkdir(parents=True, exist_ok=True)

    def _get(self, url: str, params: dict | None = None, raw: bool = False):
        params = None if raw else {**(params or {}), "format": "json"}
        cache_key = hashlib.sha1(f"{url}{sorted((params or {}).items())}".encode()).hexdigest()
        path = CACHE / f"{cache_key}.{'txt' if raw else 'json'}"
        if path.exists():
            body = path.read_text(encoding="utf-8")
            return body if raw else json.loads(body)
        headers = None if raw else {"X-Api-Key": self.key}
        for attempt in range(4):
            r = self.http.get(url, params=params, headers=headers)
            if r.status_code == 429:
                time.sleep(2 ** attempt * 5)
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError(f"rate limited: {url}")
        time.sleep(self.pause)
        path.write_text(r.text, encoding="utf-8")
        return r.text if raw else r.json()

    def list_bills(self, congress: int, bill_type: str, limit: int = 250, max_pages: int = 4):
        out = []
        for page in range(max_pages):
            data = self._get(f"{BASE}/bill/{congress}/{bill_type}", {"limit": limit, "offset": page * limit})
            out += data.get("bills", [])
            if not data.get("pagination", {}).get("next"):
                break
        return out

    def summaries(self, congress, bill_type, number):
        return self._get(f"{BASE}/bill/{congress}/{bill_type}/{number}/summaries").get("summaries", [])

    def text_versions(self, congress, bill_type, number):
        return self._get(f"{BASE}/bill/{congress}/{bill_type}/{number}/text").get("textVersions", [])

    def fetch_text(self, formats: list[dict]) -> str | None:
        fmt = next((f for f in formats if f["type"] == "Formatted Text"), None)
        if not fmt:
            return None
        return html_to_text(self._get(fmt["url"], raw=True))


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()


def html_summary_to_text(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ")).strip()


def match_version(summary: dict, text_versions: list[dict]):
    """Pick the text version that corresponds to the CRS summary's stage.

    Returns (text_version, method) or (None, None). Exact stage match first; otherwise the
    latest text version dated on/before the summary's action date. Undated versions are ignored.
    """
    action = _norm(summary.get("actionDesc", ""))
    wanted = _STAGE_ALIASES.get(action, [action])
    dated = [v for v in text_versions if v.get("date")]
    for v in dated:
        if _norm(v["type"]) in wanted:
            return v, "exact"
    on_or_before = [v for v in dated if v["date"][:10] <= summary.get("actionDate", "")[:10]]
    if on_or_before:
        return max(on_or_before, key=lambda v: v["date"]), "date_fallback"
    return None, None
