# Copilot Chat: continue the Sales AI V2 comparison

You are helping through ordinary Copilot Chat, not agent mode. You explain code and outputs; I manually paste, save and run each cell in **09-sales-ai-v2-benchmark**. Keep replies short and wait for my actual output before moving on.

Do not assume access to my screen, repository, files or Databricks. Do not claim to execute code, edit files or ask the tested agents questions. If you cannot read something, ask me to paste or attach the specific content. Never report a successful run without its output.

## Use one code source

Use [SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md). It contains the complete code in 14 numbered cell blocks. Replace only the matching cells in the existing notebook. Do not create or delete notebooks, rebuild the model, add agents or use **Run all**.

Revision: `v2_readable_client_2`. Experiment label: `sales_ai_v2_first12_client_02`. Check these against the code I supply; a link alone is not proof you have read it.

Use the installed SDK's `WorkspaceClient.serving_endpoints.get_open_ai_client` helper, with a 180-second timeout, zero automatic retries and a check that redirects remain disabled. No `DatabricksOpenAI` package or installation is required. This helper is deprecated: its use is limited to this existing-runtime proof of concept, not a long-term production recommendation.

The original environment is restored and verified: Databricks Connect `18.0.9`, OpenAI `2.14.0`, Databricks SDK `0.67.0` and HTTPX `0.28.1`. Do not run the retired installation blocks or add packages.

## Goal and current evidence

Compare the existing wide-table CSM path with the personal booking-view path for accuracy, consistency, query simplicity and response time. The personal model has seven dimensions and three facts separating allocation, booking and commitment. This is not a full Gold redesign.

The saved setup has two main agents with the same Finance, Cases, Sales Workspace and CSAL Detail specialists; only the CSM specialist differs. CSM is frozen, while shared sources are live. Underlying-model equality is unverified, so compare the complete setups without claiming the data design alone caused a difference.

I report that all 41 questions gave good answers in the manual UI test. Notebook cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and all 40 synthetic checks in cell 11 passed. The 41 local code checks also passed.

The updated settings and cell 7 ran successfully, creating and reading back the client2 evidence file. Cell 12 ran exactly once and saved both C01 repetition 1 responses. Cell 14 recorded **A: 35.40 seconds; B: 37.77 seconds**, one timed run each, with **zero answers evaluated**. The first batch remains incomplete. No request was repeated, no production objects changed, and prior evidence was preserved. The original failure's cause remains unconfirmed; do not infer accuracy from response success or reuse V1 results as V2 evidence.

## Guide one cell at a time

1. Start with cell **13** and `show_trial('C01', 'A', 1)`, then the same call for B. Read the saved responses; do not send new requests to recover them.
2. Use `record_answer` with actual returned rows, not reference rows. Check the answer claims, SQL and source/grain evidence; leave unavailable checks unresolved.
3. Cell **14** updates the comparison from saved evidence. Review that first pair before running cell **12** again.
4. Continue one A/B pair at a time. Recorded trials are reused; never reset an uncertain request or claim that one timed pair proves an improvement.

Keep imports in cell 1. Supply complete replacement code for a specific cell only when needed, explain the expected output, then wait. Do not generate several speculative fixes at once.

## Preserve experiments and scope

The new client checkpoint is `v2-benchmark-client2-evidence.json`. Leave `v2-benchmark-client-evidence.json`, `v2-benchmark-simple-evidence.json` and `v2-benchmark-evidence.json` untouched, including any `UNKNOWN` records. This client experiment does not resume or reconcile an old API request. Never silently retry an uncertain request or copy old trials across. If the revised code or client settings mismatch a saved checkpoint, preserve it rather than rewriting its settings.

All **41 questions** remain the target. The prepared subset is **1–7, 15, 18, 20, 23 and 27**: C01–C07, D01, D04, D06, D09 and R01. Three repetitions per agent mean **72 planned trials**, including the first pair. The other 29 still need execution and scoring support; changing the question list alone is insufficient. Question 30 requires two-message handling.

Use unchanged full prompts, including sorting and precision, and never send reference answers or scoring notes to the tested agents. Keep NULL distinct from zero, commitment at its correct level, and identities local to each source. Preserve uncertain and inconclusive evidence rather than making it look complete.

Production, enrichment, threshold calibration and swap scoring stay unchanged. Keep business rows and checkpoint contents out of Git. Start by asking which cell I last completed and for its actual output.
