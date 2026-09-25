# Decisions log

Each entry: what was decided, why, and what was rejected. Newest at the bottom.
This file doubles as source material for the README, the findings page and the video.

## Step 1: Data pipeline (Congress.gov)

**How the API is shaped.** A bill is addressed by `congress / type / number` (e.g. `119/hr/1234`).
The bill list endpoint returns metadata only. Text and summaries are separate sub-resources:
- `/summaries` returns CRS summaries, each tagged with a stage (`actionDesc`, e.g. "Introduced in House", "Passed House") and an `actionDate`. A bill can have several, written at different stages.
- `/text` returns text versions (Introduced, Reported, Engrossed, Enrolled...), each with links to HTML, PDF and XML.
So a bill has many summaries and many texts, and there is no built-in pairing between them.

**Decision: pair each summary with the text from the same stage.**
Why: if the CRS summary describes the enrolled bill but the model reads the introduced text, provisions differ and the model gets marked wrong for being right. That would poison every metric.
How: match the summary's stage to the text version's type (exact), else use the latest text dated on or before the summary (date fallback). Each row records which method was used, so the fallback rows can be audited or dropped.
Rejected: always using the latest text. Simple, but it silently mismatches.

**Decision: use the latest CRS summary per bill.** It is the most complete. The text is matched to it, not the other way round.

**Decision: 119th Congress only.** Recent bills are less likely to be in model training data, so scores reflect summarizing, not recall. Caveat to state in the findings: this reduces contamination, it does not remove it.

**Decision: stratify by token count (short/medium/long), 20 each, seed 42.** Length is the biggest driver of summarization quality and cost. A single average would hide that a small model collapses on long bills. Fixed seed for reproducibility. Token count uses tiktoken cl100k, which is approximate and only used for bucketing.

**Decision: cache every API response on disk (`data/raw`, gitignored).** Reruns are free, we stay under rate limits, and the dataset can be rebuilt without re-fetching.

**Decision: commit `data/bills.jsonl` later, not `data/raw`.** The built dataset is the benchmark. Raw cache is just plumbing.

**Decision: Python 3.11+, pydantic schema, typer CLI, pytest for the matching logic.** The matching is the piece most likely to be silently wrong, so it is the piece with tests.

**Open item:** pipeline is untested against the live API. Stage aliases in `congress.py` may need adjusting after the first real run.
