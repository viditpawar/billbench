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

## Step 2 planning: zero-cost stack

**Decision: build the benchmark on free and open models only.** Tested: llama3.2:3b and a Qwen model (local, Ollama), Llama 3.3 70B (Groq free tier). Judge: Gemini Flash (free tier).
Why: the question becomes "how far can free and open models go on bill summarization, and where exactly do they fail", which is the real question for a cost-conscious early startup. The rigor of the eval matters more than the price of the models.
Judge independence: Google judge vs Meta/Alibaba candidates, so the judge is never grading its own family. Caveat: llama3.2:3b and Llama 3.3 70B share a family, so the size comparison is cleaner than the vendor comparison.
The harness stays config driven, so adding a frontier model later is a few lines of YAML. The README should say this openly.

**Decision: still report cost per bill.** Free models cost $0, so the cost column also shows "hypothetical cost at list price" computed from real token counts. Otherwise the "what does it cost per document" question would have no answer.

**Decision: retries with backoff, and cache every completed generation and judgment.** Free tiers rate limit, so a failed run must resume, not restart.

**Risk to check first:** Groq's free tier caps tokens per minute and per request. Long bills (up to ~60k tokens) may be rejected outright. Options: lower the long-bucket ceiling, or report those cases as "could not run" (itself a finding). Decide after checking current Groq limits.

**Decision: local Qwen is qwen2.5:7b, not qwen3.** Qwen3 has a thinking mode that emits long reasoning before the answer, which inflates latency and output tokens and adds noise to the cost/latency comparison. qwen2.5 gives a clean like-for-like measurement.

**Decision: context length is explicit and truncation is never silent.** `num_ctx` is set per model in YAML. If a bill's prompt exceeds a model's limit, the result is flagged `truncated` and reported by length bucket. Ollama truncating silently would make a 3B model look like it "summarized" a long bill when it only read the start.

## Step 1 results: first live dataset build

Built 54 bills (short 20, medium 20, long 14) from the 119th Congress. 52 matched the CRS stage exactly, 2 used the date fallback.

**Finding: only 14 long bills exist in the pool.** Most long bills (omnibus, appropriations, reconciliation) have no CRS summary yet, or exceed the 60k token ceiling. Decision: keep 54 and report the long bucket as n=14 instead of loosening the criteria. Sample size per bucket goes in the findings page.

**Finding: the API names one text stage "Reported to Senate", not "Reported in Senate".** The alias table missed it, which is why 2 bills fell back to the date method. Fixed by adding the alias. Rerun the build to confirm they become exact matches.

**Known issue: CRS summaries start with the bill title** (e.g. "No Track No Tax Act of 2025 This bill prohibits..."). The title is not a claim about provisions, so scoring coverage against it is slightly inflated. To handle in the coverage metric, by stripping the title prefix before extracting key provisions.

**Observation:** 100% of texts are introduced or reported versions. CRS mostly summarizes at introduction, so the benchmark measures summarizing bills as introduced, not as enacted.
