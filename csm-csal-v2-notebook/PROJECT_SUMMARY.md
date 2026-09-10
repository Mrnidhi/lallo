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

Revision `v2_routing_contract_1` uses the installed SDK's `WorkspaceClient.serving_endpoints.get_open_ai_client` helper: a 180-second timeout, zero automatic retries and a check that redirects remain disabled. It needs no additional `DatabricksOpenAI` package or installation. The helper is deprecated; this is a contained proof of concept using the existing runtime, not a long-term production recommendation.

The new experiment label is `sales_ai_v2_first12_routing_01`, using `v2-benchmark-routing1-evidence.json`. All earlier evidence files, including `v2-benchmark-client2-evidence.json`, stay untouched, including uncertain requests. Preserve any checkpoint mismatch; do not rewrite saved settings to fit this revision. The routing experiment does not resume or reconcile an old API call.

Both personal supervisors now have the same saved routing text. It was manually read back after refresh and matched SHA-256 `34e216...a7398`. A routes weekly customer, agreement and TCR CSM summaries to **CSM Wide Baseline V2**; B routes the same scope to **CSM Booking Scope V2**. Detail remains for booking-level drill-down only. The notebook records this contract but does not fetch the UI configuration itself.

## Where we stand

Manual UI answers are useful informal evidence, but they are not counted as a verified 41-question benchmark. In the notebook, cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and cell 11 passed all 40 synthetic scorer checks for the earlier revision.

The original environment is restored and verified: Databricks Connect `18.0.9`, OpenAI `2.14.0`, Databricks SDK `0.67.0` and HTTPX `0.28.1`. Do not run the retired installation blocks or add packages.

The updated settings and cell 7 created and read back the separate client2 evidence file. Cell 12 ran exactly once and saved both C01 repetition 1 responses. Cell 13 then compared the original saved Markdown values and recorded only previously unreviewed answers. Cell 14 reports:

| First C01 pair | Before (A) | After (B) |
|---|---:|---:|
| Received / evaluated / correct | 1 / 1 / 0 | 1 / 1 / 0 |
| Returned rows | 20 | 20 |
| Expected customer/agreement/TCR keys present | 4 of 20 | 4 of 20 |
| Internally consistent utilization ratios | 20 of 20 | 20 of 20 |
| Client response time | 35.40 seconds | 37.77 seconds |

Both row results are `INCORRECT` against the frozen CSM reference. Display-header contract compliance is also false, but that is separate from the row mismatch. The arithmetic fits each returned row; that does not establish the correct source, commitment denominator or answer population.

Both agents used the same allowed **CSAL Detail V2** reader. The original SQL, visually read in their saved Genie conversations, queries `dev.crmi_gold.csal_teu_performance` and aggregates confirmed and reviewed TEU by customer, agreement and TCR for the requested week/service. A uses no CTEs or joins; B uses one CTE and no joins. These queries did not exercise the differing frozen CSM and booking-view paths. SQL execution times are unavailable, and structured SQL, source and grain verdicts remain `NOT_EVALUABLE`.

This is a metric-source/routing mismatch in our personal comparison, not proof of a production fault or an access violation. No architecture winner can be inferred from this pair.

All 41 local code checks passed. The original API failure's cause remains unconfirmed. Only saved-response review and reporting were rerun, with zero new questions. No request was repeated, production was unchanged, and all earlier evidence was preserved.

## What remains

All **41 questions** remain the target.

1. Prepare the new `routing_01` experiment with cells 1–11 and submit one A/B pair only. Check the saved response, reader route and returned rows before continuing. Do not rebuild tables or change production.
2. Preserve this first pair and its reference answers. Do not redefine the expected answer to match what the agents returned. Complete any further SQL, source, grain or claim review from saved evidence only; unavailable checks remain unresolved.
3. After reviewing the first routing_01 pair, continue the controlled comparison. The prepared questions are **1–7, 15, 18, 20, 23 and 27**: 12 questions, three repetitions per agent, **72 planned trials**. The new routing_01 experiment begins with all 72 unsubmitted. It must not silently inherit the earlier client2 trials.
4. Add execution and scoring support for the remaining 29 in the same notebook. Question 30 needs two-message handling. Keep clarification, limitation and pending outcomes separate from numerical accuracy.

The complete target is **246 question-level evaluations**, plus additional message turns for question 30. It is not completed or fully supported work. Preserve first-batch evidence when extending the plan, and never silently resend uncertain requests.

Production, enrichment, historical threshold calibration and swap scoring remain unchanged. Missing SQL, claim checks, source/grain evidence and timing must remain unavailable or incomplete, not invented.

Next: use [the cell-by-cell code](SALES_AI_V2_BENCHMARK.md). The [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md) is for advice and code suggestions only; the user manually pastes and runs each cell and shares the actual output.
