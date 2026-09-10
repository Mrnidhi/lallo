Zx # Sales AI V2 benchmark

Start with [SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md). It contains the complete revised notebook, one Python block per cell.

Use the existing personal **09-sales-ai-v2-benchmark** notebook. Run cells individually. Cell 12 sends one A/B pair by default; cell 13 records the actual answers and cell 14 shows the comparison.

Revision: `v2_routing_contract_1`. Experiment label: `sales_ai_v2_first12_routing_01`. This uses a separate `v2-benchmark-routing1-evidence.json` file. Preserve all earlier evidence files, including `v2-benchmark-client2-evidence.json`; do not treat the new run as recovery of an old request.

For this revision, both personal supervisors have the same saved routing instructions. They were manually read back after refresh and matched fingerprint `34e216...a7398`. Agent A uses **CSM Wide Baseline V2** for CSM summaries; agent B uses **CSM Booking Scope V2**. The shared readers remain the same.

The standalone notebook scripts and old troubleshooting instructions have been replaced by this single code document. Earlier Git versions remain recoverable from history. Databricks notebooks, tables, agents and saved results were not deleted.

The original environment is restored and verified: Databricks Connect `18.0.9`, OpenAI `2.14.0`, Databricks SDK `0.67.0` and HTTPX `0.28.1`. Cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and all 40 synthetic checks in cell 11 passed.

The first C01 pair is saved and evaluated: **each agent has 1 received, 1 evaluated and 0 correct answers** against the frozen CSM reference. Both returned 20 rows, but only 4 of the 20 expected customer/agreement/TCR keys matched. Their arithmetic was internally consistent in all 20 rows; the problem is not simply a percentage calculation or display-header difference. Response times were **A: 35.40 seconds; B: 37.77 seconds**.

Both agents used the same allowed **CSAL Detail V2** reader instead of their different CSM readers. This pair therefore does not test the intended wide-table versus booking-view difference. It is not a production diagnosis or a security violation. Original SQL was read in the saved conversations; SQL duration and structured SQL/source/grain verdicts remain unavailable or `NOT_EVALUABLE`.

The first C01 pair remains historical evidence. Do not rerun or overwrite it. The new routing-contract experiment is ready to prepare: replace cells 2 and 7 with the matching blocks, run cells 1–11 individually, then send only one new A/B pair. No rebuild is needed. Production and prior evidence remain unchanged.

The target remains 41 questions. The earlier client2 batch has 70 unsubmitted trials; the new routing_01 batch begins with all 72 trials unsubmitted. The remaining 29 questions need test support. All 41 local code checks passed. See the project summary for the first-pair findings; these results do not establish an architecture winner.

## Supporting documents

- [Project goal and current position](PROJECT_SUMMARY.md)
- [All 41 business questions](question_bank.md)
- [Production and V2 diagrams](OBSIDIAN_PRODUCTION_AND_V2.md)
- [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md)
