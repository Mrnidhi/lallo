# Copilot Chat: continue the Sales AI V2 comparison

You are helping through ordinary Copilot Chat, not agent mode. You explain code and outputs; I manually paste, save and run each cell in **09-sales-ai-v2-benchmark**. Keep replies short and wait for my actual output before moving on.

Do not assume access to my screen, repository, files or Databricks. Do not claim to execute code, edit files or ask the tested agents questions. If you cannot read something, ask me to paste or attach the specific content. Never report a successful run without its output.

## Use one code source

Use [SALES_AI_V2_BENCHMARK.md](SALES_AI_V2_BENCHMARK.md). It contains the complete code in 14 numbered cell blocks. Replace only the matching cells in the existing notebook. Do not create or delete notebooks, rebuild the model, add agents or use **Run all**.

Revision: `v2_routing_contract_1`. Experiment label: `sales_ai_v2_first12_routing_01`. Check these against the code I supply; a link alone is not proof you have read it.

Use the installed SDK's `WorkspaceClient.serving_endpoints.get_open_ai_client` helper, with a 180-second timeout, zero automatic retries and a check that redirects remain disabled. No `DatabricksOpenAI` package or installation is required. This helper is deprecated: its use is limited to this existing-runtime proof of concept, not a long-term production recommendation.

The original environment is restored and verified: Databricks Connect `18.0.9`, OpenAI `2.14.0`, Databricks SDK `0.67.0` and HTTPX `0.28.1`. Do not run the retired installation blocks or add packages.

## Goal and current evidence

Compare the existing wide-table CSM path with the personal booking-view path for accuracy, consistency, query simplicity and response time. The personal model has seven dimensions and three facts separating allocation, booking and commitment. This is not a full Gold redesign.

The saved setup has two main agents with the same Finance, Cases, Sales Workspace and CSAL Detail specialists; only the CSM specialist differs. CSM is frozen, while shared sources are live. Underlying-model equality is unverified, so compare the complete setups without claiming the data design alone caused a difference.

Manual UI answers are informal evidence only. Do not report them as a verified 41-question benchmark. Notebook cells 1–6 passed, cell 8 confirmed both connections are ready, cells 9–10 loaded, and all 40 synthetic checks in cell 11 passed for the earlier revision. The 41 local code checks also passed.

The client2 evidence file was created and read back. Cell 12 ran once, saving C01 repetition 1 from both agents. Cell 13 compared the original saved Markdown values and recorded only previously unreviewed answers. Cell 14 now shows **each agent: 1 received, 1 evaluated, 0 correct** against the frozen CSM reference. Both returned 20 rows, with only 4 of the 20 expected customer/agreement/TCR keys present. All 20 ratios were internally consistent for each agent. Display-header compliance was false separately from the row mismatch. Client response times were **A: 35.40 seconds; B: 37.77 seconds**.

Both used the same allowed **CSAL Detail V2** reader. The original SQL was visually read in the saved Genie conversations: both query `dev.crmi_gold.csal_teu_performance` and aggregate confirmed/reviewed TEU by customer, agreement and TCR for the requested week/service. A has no CTEs or joins; B has one CTE and no joins. SQL duration is unavailable; structured SQL, source and grain verdicts remain `NOT_EVALUABLE`.

This pair did not test the intended difference between the frozen CSM table and booking view. Treat it as a metric-source/routing mismatch in our personal benchmark, not a production diagnosis or security violation. Only saved-response review and reporting were rerun, with zero new questions. No request was repeated; production and earlier evidence remain unchanged. The original connection failure's cause remains unconfirmed.

For the next experiment, both personal supervisors have the same saved routing text, manually read back after refresh with fingerprint `34e216...a7398`. Agent A uses **CSM Wide Baseline V2** for weekly customer, agreement and TCR CSM summaries. Agent B uses **CSM Booking Scope V2** for the same scope. CSAL Detail V2 is limited to individual booking drill-down. The old C01 client2 pair stays historical evidence.

## Guide one cell at a time

1. Replace cells 2 and 7 with the matching routing_01 blocks. Run cells 1–11 individually, then run cell 12 once for one new A/B pair. Do not rebuild tables automatically.
2. Preserve the original C01 trials and expected answers. Never change the reference to match observed answers or copy expected rows into actual evidence. Further inspection should use the saved responses, not new questions.
3. Keep SQL, source, grain and answer-claim checks unresolved until supported by evidence. Cell **14** can report saved results without sending agent requests.
4. Follow the routing_01 plan one pair at a time. Do not mix instruction versions or silently reset uncertain requests.

Keep imports in cell 1. Supply complete replacement code for a specific cell only when needed, explain the expected output, then wait. Do not generate several speculative fixes at once.

## Preserve experiments and scope

The new routing checkpoint is `v2-benchmark-routing1-evidence.json`. Leave `v2-benchmark-client2-evidence.json`, `v2-benchmark-client-evidence.json`, `v2-benchmark-simple-evidence.json` and `v2-benchmark-evidence.json` untouched, including any `UNKNOWN` records. This routing experiment does not resume or reconcile an old API request. Never silently retry an uncertain request or copy old trials across. If the revised code or client settings mismatch a saved checkpoint, preserve it rather than rewriting its settings.

All **41 questions** remain the target. The prepared subset is **1–7, 15, 18, 20, 23 and 27**: C01–C07, D01, D04, D06, D09 and R01. Three repetitions per agent mean **72 planned trials**. The earlier client2 experiment has two submitted C01 trials and 70 unsubmitted trials; the routing_01 experiment starts with all 72 trials unsubmitted. The other 29 questions still need execution and scoring support; changing the question list alone is insufficient. Question 30 requires two-message handling.

Use unchanged full prompts, including sorting and precision, and never send reference answers or scoring notes to the tested agents. Keep NULL distinct from zero, commitment at its correct level, and identities local to each source. Preserve uncertain and inconclusive evidence rather than making it look complete.

Production, enrichment, threshold calibration and swap scoring stay unchanged. Keep business rows and checkpoint contents out of Git. Start with the routing decision above, not another benchmark run.
