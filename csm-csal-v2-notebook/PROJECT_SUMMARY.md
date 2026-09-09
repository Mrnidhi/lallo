# CSM / CSAL V2: goal and current position

Updated: 9 September 2026

## Why we started

We want sales agents to answer business questions more accurately and consistently, with simpler SQL and, if testing supports it, faster responses.

Some straightforward questions were producing long queries or incorrect answers. We are testing whether clearer data organization helps. A wide table is not automatically bad, and a fact/dimension design is not automatically faster.

## What is built

The personal CSM model has seven dimension tables and three fact tables, separating allocation, booking and commitment figures. A booking view provides the agent’s query interface. Saved relationship, row-count and measure checks passed.

Two existing main agents provide the comparison:

- **Before:** the frozen wide-table baseline through its CSM specialist.
- **After:** the booking view over the personal fact/dimension model through its CSM specialist.

Both use the same four shared specialists for finance, cases, sales workspace information and CSAL detail. Only the CSM specialist differs. This is a CSM proof of concept, not a redesign of every Gold domain. Production stays unchanged.

The source data is not one common historical snapshot: CSM is frozen, while shared sources are live. Databricks manages the underlying models, and model equality is unverified. Results must compare the complete setups, not attribute every difference to the data design alone.

## One readable notebook handoff

[SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md) is the code source: one Markdown file containing all 14 numbered cells. Paste each block into its matching cell in the existing **09-sales-ai-v2-benchmark** notebook. No notebook needs to be created or deleted.

Revision `v2_readable_client_1` keeps the reference calculations, source/grain checks, saved results and restart protection. It uses the official `DatabricksOpenAI` client with an explicit workspace, no automatic retries and no redirects. Compatible `databricks-openai>=0.17` and `openai<3` packages are required; nothing is installed automatically.

The experiment is `sales_ai_v2_first12_client_01`, saved in `v2-benchmark-client-evidence.json`. Both older evidence files (`v2-benchmark-simple-evidence.json` and `v2-benchmark-evidence.json`) stay untouched, including uncertain requests. This is a new client experiment, not a resumed or reconciled old API call.

## Where we stand

The user reports good answers for all 41 questions in a manual UI test. Both endpoint metadata GET checks succeeded, and earlier reference preparation passed. These observations are useful, but there are no verified, scored V2 benchmark results yet.

The original API request failure's cause is still unconfirmed. The client revision has not been verified in Databricks, so it is not a guaranteed fix. A successful metadata check does not prove a question can be submitted successfully; passing reference checks does not certify business policy.

## What remains

All **41 questions** remain the target.

1. Paste the 14 code blocks into the matching cells. Run imports/settings in cells 1–2 and reference checks in cells 3–6 individually, stopping on errors.
2. Save the personal checkpoint in cell 7, check metadata and prepare the client in cell 8, then load the runner/scorer and run synthetic tests in cells 9–11.
3. Run cell 12 for one A/B pair by default. In cell 13, inspect `show_trial` and record actual rows with `record_answer`; no mandatory approval form is needed.
4. Use cell 14 to inspect the evidence, then continue the same experiment one pair at a time. The prepared questions are **1–7, 15, 18, 20, 23 and 27**: 12 questions, three repetitions per agent, **72 planned trials** including the first pair.
5. Add execution and scoring support for the remaining 29 in the same notebook. Question 30 needs two-message handling. Keep clarification, limitation and pending outcomes separate from numerical accuracy.

The complete target is **246 question-level evaluations**, plus additional message turns for question 30. It is not completed or fully supported work. Preserve first-batch evidence when extending the plan, and never silently resend uncertain requests.

Production, enrichment, historical threshold calibration and swap scoring remain unchanged. Missing SQL, claim checks, source/grain evidence and timing must remain unavailable or incomplete, not invented.

Next: use [the cell-by-cell code](SALES_AI_V2_BENCHMARK.md). The [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md) is for advice and code suggestions only; the user manually pastes and runs each cell and shares the actual output.
