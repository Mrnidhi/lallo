# Copilot Chat handoff: CSM / CSAL V2

Use this as context in ordinary Copilot Chat.

## Prompt

I am reviewing a completed, read-only CSM/CSAL personal proof of concept in Databricks. Do not change production, rebuild tables, edit agents, resend benchmark questions or modify saved evidence.

The goal was to compare a frozen 78-column Gold-shaped CSM source with a smaller 29-column booking view over a validated personal fact-and-dimension model. Agent A used the wide source. Agent B used the curated booking view. Both personal main agents had the same other four specialist readers.

The controlled test used C01-C07, three repetitions per question and agent, for 42 completed responses. The reference calculations were technically cross-checked for the frozen snapshot, but current business thresholds are not business-owner approved.

Final results:

- Wide A: 12 proven-correct answers out of 21 planned runs
- Curated B: 13 proven-correct answers out of 21 planned runs
- Accuracy across the 18 C01-C06 table-answer runs: 66.7% for A and 72.2% for B
- Stable comparable question groups: 3 of 4 for both
- Median client response time: 40.98 seconds for A and 40.09 seconds for B
- C07 clear no-match statements: 3 of 3 for both, but exact retrieval was not proven because executed SQL was unavailable
- SQL correctness, actual source routing, SQL execution time and SQL complexity: not evaluated

Most misses came from one unstable C01 ranking, missing recognizable agreement fields in C03, and missing recognizable confirmed-TEU fields in C06. The curated path was only one answer better, so do not claim a decisive architecture win.

The recommendation is to keep production unchanged, keep the curated booking view as a pilot, tighten the response contract for C01, C03 and C06, capture structured executed-SQL evidence and rerun the same controlled test under a new version.

The Databricks-managed model identity and actual per-request warehouse use were not independently verified. Compare the complete setups and do not say the fact/dimension design alone caused the difference.

The 41-question bank, hard-scenario bank, historical threshold calibration, actual-event enrichment and swap scoring are later phases. Do not describe them as completed.

If I paste a notebook output, explain only what it proves and what it does not prove. Keep the response short, clear and non-technical. Never invent a successful run or missing evidence.

## Safe review cells

The completed notebook already contains all results. Cells `49` to `53` are read-only review and report cells. Cells `47` and `48` send requests and must not be rerun. Do not use Run All.
