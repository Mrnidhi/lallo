# Sales AI V2 benchmark

Start with [SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md). It contains the complete revised notebook, one Python block per cell.

Use the existing personal **09-sales-ai-v2-benchmark** notebook. Run cells individually. Cell 12 sends one A/B pair by default; cell 13 records the actual answers and cell 14 shows the comparison.

Revision: `v2_readable_client_2`. It uses the installed SDK's `get_open_ai_client` helper, a 180-second timeout, zero automatic retries and a check for disabled redirects. No extra package installation is needed. The helper is deprecated and used only for this contained proof of concept, not as a long-term production recommendation.

The new label is `sales_ai_v2_first12_client_02`, using `v2-benchmark-client2-evidence.json`. Preserve all three earlier evidence files, including `v2-benchmark-client-evidence.json`, and all uncertain requests. A changed-code checkpoint mismatch must be investigated, not overwritten.

The original environment is restored and verified: Databricks Connect `18.0.9`, OpenAI `2.14.0`, Databricks SDK `0.67.0` and HTTPX `0.28.1`. Do not run the retired installation blocks or add packages.

Cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and all 40 synthetic checks in cell 11 passed. The updated settings and cell 7 ran successfully; the client2 evidence file was created and read back.

The first C01 pair is saved and evaluated: **each agent has 1 received, 1 evaluated and 0 correct answers** against the frozen CSM reference. Both returned 20 rows, but only 4 of the 20 expected customer/agreement/TCR keys matched. Their arithmetic was internally consistent in all 20 rows; the problem is not simply a percentage calculation or display-header difference. Response times were **A: 35.40 seconds; B: 37.77 seconds**.

Both agents used the same allowed **CSAL Detail V2** reader instead of their different CSM readers. This pair therefore does not test the intended wide-table versus booking-view difference. It is not a production diagnosis or a security violation. Original SQL was read in the saved conversations; SQL duration and structured SQL/source/grain verdicts remain unavailable or `NOT_EVALUABLE`.

**Pause new submissions.** The next decision is whether to clarify CSM routing equally in both personal supervisors and start a new instruction/experiment version. Keep the original trial, evidence and expected answers unchanged; no rebuild is needed. Cell 13 reviewed the original saved answers, and cell 14 reported them without new questions. Production and prior evidence remain unchanged.

The standalone notebook scripts and old troubleshooting instructions have been replaced by this single code document. Earlier Git versions remain recoverable from history. Databricks notebooks, tables, agents and saved results were not deleted.

The target remains 41 questions. Of 72 planned trials for the first 12 questions, **70 are still unsubmitted**. The remaining 29 questions need test support. All 41 local code checks passed. See the project summary for the first-pair findings; these results do not establish an architecture winner. The original API failure's cause remains unconfirmed.

## Supporting documents

- [Project goal and current position](PROJECT_SUMMARY.md)
- [All 41 business questions](question_bank.md)
- [Production and V2 diagrams](OBSIDIAN_PRODUCTION_AND_V2.md)
- [Copilot Chat handoff](OFFICE_COPILOT_HANDOFF.md)
