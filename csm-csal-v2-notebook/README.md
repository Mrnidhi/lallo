# Sales AI V2 benchmark

Start with [SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md). It contains the complete revised notebook, one Python block per cell.

Use the existing personal **09-sales-ai-v2-benchmark** notebook. Run cells individually. Cell 12 sends one A/B pair by default; cell 13 records the actual answers and cell 14 shows the comparison.

Revision: `v2_readable_client_1`. This uses a separate `v2-benchmark-client-evidence.json` file. Do not delete either earlier evidence file or treat the new run as recovery of the old uncertain request.

The standalone notebook scripts and old troubleshooting instructions have been replaced by this single code document. Earlier Git versions remain recoverable from history. Databricks notebooks, tables, agents and saved results were not deleted.

The full target remains 41 questions. This revision has 12 prepared questions and 72 planned runs; the other 29 still need scoring support. Local tests passed. A live run of the revised client is still pending.

## Supporting documents

- [Project goal and current position](PROJECT_SUMMARY.md)
- [All 41 business questions](question_bank.md)
- [Production and V2 diagrams](OBSIDIAN_PRODUCTION_AND_V2.md)
- [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md)
