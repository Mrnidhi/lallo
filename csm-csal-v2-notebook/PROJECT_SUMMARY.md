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

Revision `v2_readable_client_2` uses the installed SDK's `WorkspaceClient.serving_endpoints.get_open_ai_client` helper: a 180-second timeout, zero automatic retries and a check that redirects remain disabled. It needs no additional `DatabricksOpenAI` package or installation. The helper is deprecated; this is a contained proof of concept using the existing runtime, not a long-term production recommendation.

The experiment label remains `sales_ai_v2_first12_client_01`, using `v2-benchmark-client-evidence.json`. Both older evidence files (`v2-benchmark-simple-evidence.json` and `v2-benchmark-evidence.json`) stay untouched, including uncertain requests. Preserve any checkpoint mismatch; do not rewrite saved settings to fit this revision. The client experiment does not resume or reconcile an old API call.

## Where we stand

The user reports good answers for all 41 questions in a manual UI test. Both endpoint metadata GET checks succeeded, and earlier reference preparation passed. These observations are useful, but there are no verified, scored V2 benchmark results yet.

The earlier optional installation downgraded Databricks Connect from 18.0.9 to 17.0.10. With the user's approval, the two added notebook dependencies were removed and the personal environment was reset. Restored package versions still need verification; do not repeat the old installation blocks.

All 41 local code checks passed. No live inference success has been verified. The original API failure's cause remains unconfirmed, and this revision is not a guaranteed fix. Metadata success does not prove inference works; reference checks do not certify business policy.

## What remains

All **41 questions** remain the target.

1. Verify the restored environment versions first. Then paste the 14 code blocks into the matching cells and run cells 1–6 individually, stopping on errors.
2. Save the personal checkpoint in cell 7, check metadata and prepare the client in cell 8, then load the runner/scorer and run synthetic tests in cells 9–11.
3. Run cell 12 for one A/B pair by default. In cell 13, inspect `show_trial` and record actual rows with `record_answer`; no mandatory approval form is needed.
4. Use cell 14 to inspect the evidence, then continue the same experiment one pair at a time. The prepared questions are **1–7, 15, 18, 20, 23 and 27**: 12 questions, three repetitions per agent, **72 planned trials** including the first pair.
5. Add execution and scoring support for the remaining 29 in the same notebook. Question 30 needs two-message handling. Keep clarification, limitation and pending outcomes separate from numerical accuracy.

The complete target is **246 question-level evaluations**, plus additional message turns for question 30. It is not completed or fully supported work. Preserve first-batch evidence when extending the plan, and never silently resend uncertain requests.

Production, enrichment, historical threshold calibration and swap scoring remain unchanged. Missing SQL, claim checks, source/grain evidence and timing must remain unavailable or incomplete, not invented.

Next: use [the cell-by-cell code](SALES_AI_V2_BENCHMARK.md). The [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md) is for advice and code suggestions only; the user manually pastes and runs each cell and shares the actual output.
