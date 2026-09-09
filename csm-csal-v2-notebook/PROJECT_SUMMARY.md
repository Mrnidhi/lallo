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

## What is simpler now

Use the same **09-sales-ai-v2-benchmark** notebook, with the same 14 files and cells.

The new `v2_simple_runner_1` revision removes manual review flags, enabling switches and request-schema setup. Cell 7 automatically checks preparation and source versions, then saves or resumes the separate `v2-benchmark-simple-evidence.json` checkpoint. The old evidence file is not deleted or reused for this new experiment.

Both request formats are preconfigured from observed endpoint examples. Cell 8 checks Ready endpoints without OpenAPI discovery. Manually running cell 12 sends at most one A/B pair. Saved trials are reused on continuation. Cell 13 helps record actual returned answers; cell 14 shows the comparison without inventing missing SQL or timing.

Earlier reference-answer preparation passed its checks. This simplified revision passed local regression and synthetic scoring tests but still needs a verified Databricks run. There are no verified V2 benchmark results to report. Automatic checks do not establish business correctness.

## What remains

All **41 questions** remain the target.

1. Replace the matching cells, run preparation individually and inspect the reference logic.
2. Save the simple checkpoint, check endpoints and run the scorer tests.
3. Run one pair and inspect both original answers and available SQL.
4. Complete the unchanged first 12 questions, three times per agent: **72 trials**, including that first pair.
5. Add execution and scoring support for the remaining 29 in the same notebook. Question 30 needs two-message handling. Keep clarification, limitation and pending outcomes separate from numerical accuracy.

The complete plan is **246 question-level evaluations** across both agents and three repetitions, with additional message turns for question 30. That is a target, not completed or fully supported work. Preserve first-batch evidence separately when adding the larger plan.

Enrichment, historical threshold calibration and swap scoring remain parked. No new production tables, agents or framework are needed to start the first pair.

Next: follow the [short run guide](README.md). Use [cell 7 help](CHECK_CELL_7.md) only if it stops. The [Copilot handoff](OFFICE_COPILOT_HANDOFF.md) keeps the full 41-question goal explicit.
