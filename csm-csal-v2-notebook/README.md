# Sales AI V2 benchmark

Start with [SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md). It contains the complete revised notebook, one Python block per cell.

Use the existing personal **09-sales-ai-v2-benchmark** notebook. Run cells individually. Cell 12 sends one A/B pair by default; cell 13 records the actual answers and cell 14 shows the comparison.

Revision: `v2_readable_client_2`. It uses the installed SDK's `get_open_ai_client` helper, a 180-second timeout, zero automatic retries and a check for disabled redirects. No extra package installation is needed. The helper is deprecated and used only for this contained proof of concept, not as a long-term production recommendation.

The new label is `sales_ai_v2_first12_client_02`, using `v2-benchmark-client2-evidence.json`. Preserve all three earlier evidence files, including `v2-benchmark-client-evidence.json`, and all uncertain requests. A changed-code checkpoint mismatch must be investigated, not overwritten.

The original environment is restored and verified: Databricks Connect `18.0.9`, OpenAI `2.14.0`, Databricks SDK `0.67.0` and HTTPX `0.28.1`. Do not run the retired installation blocks or add packages.

Cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and all 40 synthetic checks in cell 11 passed. Next: transfer cells 2 and 7 for the separate results file. No agent question has been sent in this new experiment.

The standalone notebook scripts and old troubleshooting instructions have been replaced by this single code document. Earlier Git versions remain recoverable from history. Databricks notebooks, tables, agents and saved results were not deleted.

The full target remains 41 questions. This revision has 12 prepared questions and 72 planned runs; the other 29 still need scoring support. All 41 local code checks passed. No live inference success is verified, and the original API failure's cause remains unconfirmed.

## Supporting documents

- [Project goal and current position](PROJECT_SUMMARY.md)
- [All 41 business questions](question_bank.md)
- [Production and V2 diagrams](OBSIDIAN_PRODUCTION_AND_V2.md)
- [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md)
