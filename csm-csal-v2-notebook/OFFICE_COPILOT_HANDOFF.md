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

I report that all 41 questions gave good answers in the manual UI test. Notebook cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and all 40 synthetic checks in cell 11 passed. The 41 local code checks also passed. The new checkpoint still needs transfer; no agent question has been sent in this experiment. The original API failure's cause remains unconfirmed. Do not treat these checks as scored benchmark results or reuse V1 results as V2 evidence.

## Guide one cell at a time

1. Transfer the new settings and checkpoint blocks (cells **2 and 7**) into the existing notebook. Keep every previous evidence file unchanged.
2. Run cell **7** to save the separate experiment. If preparation is stale, refresh the required cells. Runtime, connection and synthetic scorer checks have already passed; no benchmark question has been sent.
3. Manually running cell **12** sends one A/B pair by default. Then run cell **13** and use `show_trial` and `record_answer` with actual returned rows. Do not introduce mandatory approval forms or fill answers from the references.
4. Cell **14** reports the saved evidence. Continue the same client experiment one pair at a time; recorded trials are reused. Missing claims, SQL, source/grain evidence or timing stay explicitly unresolved.

Keep imports in cell 1. Supply complete replacement code for a specific cell only when needed, explain the expected output, then wait. Do not generate several speculative fixes at once.

## Preserve experiments and scope

The new client checkpoint is `v2-benchmark-client2-evidence.json`. Leave `v2-benchmark-client-evidence.json`, `v2-benchmark-simple-evidence.json` and `v2-benchmark-evidence.json` untouched, including any `UNKNOWN` records. This client experiment does not resume or reconcile an old API request. Never silently retry an uncertain request or copy old trials across. If the revised code or client settings mismatch a saved checkpoint, preserve it rather than rewriting its settings.

All **41 questions** remain the target. The prepared subset is **1–7, 15, 18, 20, 23 and 27**: C01–C07, D01, D04, D06, D09 and R01. Three repetitions per agent mean **72 planned trials**, including the first pair. The other 29 still need execution and scoring support; changing the question list alone is insufficient. Question 30 requires two-message handling.

Use unchanged full prompts, including sorting and precision, and never send reference answers or scoring notes to the tested agents. Keep NULL distinct from zero, commitment at its correct level, and identities local to each source. Preserve uncertain and inconclusive evidence rather than making it look complete.

Production, enrichment, threshold calibration and swap scoring stay unchanged. Keep business rows and checkpoint contents out of Git. Start by asking which cell I last completed and for its actual output.
