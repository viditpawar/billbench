"""Build the stratified benchmark dataset (data/bills.jsonl)."""
import random
from pathlib import Path

import tiktoken
import yaml

from .congress import CongressClient, html_summary_to_text, match_version
from .schema import Bill

_enc = tiktoken.get_encoding("cl100k_base")  # approximate; used only for stratification


def count_tokens(text: str) -> int:
    return len(_enc.encode(text, disallowed_special=()))


def stratum_for(n_tokens: int, strata: dict) -> str | None:
    for name, s in strata.items():  # strata are ordered short -> long
        if n_tokens <= s["max_tokens"]:
            return name
    return None


def build(config_path="configs/eval.yaml", out="data/bills.jsonl"):
    cfg = yaml.safe_load(Path(config_path).read_text())
    sample = cfg["sample"]
    rng = random.Random(sample["seed"])
    client = CongressClient()

    candidates = []
    for bt in sample["bill_types"]:
        candidates += client.list_bills(cfg["congress"], bt)
    rng.shuffle(candidates)
    print(f"{len(candidates)} candidate bills listed")

    quota = {k: v["n"] for k, v in sample["strata"].items()}
    kept: list[Bill] = []
    for c in candidates:
        if all(q <= 0 for q in quota.values()):
            break
        bt, num = c["type"].lower(), int(c["number"])
        sums = client.summaries(cfg["congress"], bt, num)
        if not sums:
            continue
        # latest CRS summary is the most complete; the text version is matched to it
        summary = max(sums, key=lambda s: (s.get("actionDate", ""), s.get("versionCode", "")))
        tv, method = match_version(summary, client.text_versions(cfg["congress"], bt, num))
        if not tv:
            continue
        text = client.fetch_text(tv["formats"])
        if not text:
            continue
        n = count_tokens(text)
        stratum = stratum_for(n, sample["strata"])
        if not stratum or quota[stratum] <= 0:
            continue
        quota[stratum] -= 1
        kept.append(Bill(
            bill_id=f"{cfg['congress']}-{bt}-{num}", congress=cfg["congress"], bill_type=bt, number=num,
            title=c.get("title", ""), text_version=tv["type"], text_date=tv["date"], text=text,
            crs_summary=html_summary_to_text(summary["text"]), crs_version=summary.get("actionDesc", ""),
            crs_action_date=summary.get("actionDate", ""), match_method=method, n_tokens=n, stratum=stratum,
        ))
        print(f"kept {kept[-1].bill_id} [{stratum}, {n} tok, {method}] remaining={quota}")

    Path(out).parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for b in kept:
            f.write(b.model_dump_json() + "\n")
    print(f"wrote {len(kept)} bills -> {out}")
    return kept


def load(path="data/bills.jsonl") -> list[Bill]:
    return [Bill.model_validate_json(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l]
