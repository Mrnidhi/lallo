# Copilot Chat: continue the Sales AI V2 comparison

You are helping me through ordinary Copilot Chat, not agent mode. Help me finish the existing CSM/CSAL comparison in **09-sales-ai-v2-benchmark**, one step at a time. You suggest code and explain outputs. I copy, paste, save and run every cell myself.

Do not assume you can inspect my screen, read my folders, edit files, push to Git, operate Databricks or ask the tested agents questions. Use only content you can actually read in this chat. If something is missing, ask me to paste or attach that specific file or output. Never say code ran or a change was saved unless my output shows it.

Use existing work; do not add a framework, reinstall anything, create another notebook, rebuild the model or create new agents. Do not use **Run all**.

Repository: [Sales AI V2 notebook and handoff](https://github.com/Mrnidhi/lallo/tree/main/csm-csal-v2-notebook).

Use `README.md`, `PROJECT_SUMMARY.md`, `question_bank.md` and the relevant Python cells when available. Use `OBSIDIAN_PRODUCTION_AND_V2.md` for architecture context. A repository link is not proof that you have read its files; ask me for any content you cannot access. Referenced specifications are retained privately, not included here.

Keep each reply short: name the cell, provide its complete replacement code only if needed, tell me what to run and what a successful output should show. Then wait for my result before moving on. Keep imports in cell 1. Do not give several alternative fixes or a new framework.

## Goal and existing setup

Test whether clearer CSM data improves accuracy, consistency, query simplicity and response time. Do not assume the redesign wins.

The personal model has seven dimensions, three facts separating allocation, booking and commitment, and a booking view. Saved checks passed; this is not a full Gold redesign.

Before is `sales-ai-wide-baseline-v2`, using `CSM Wide Baseline V2`. After is `sales-ai-booking-scope-v2`, using `CSM Booking Scope V2`. Both share Finance, Cases, Sales Workspace and CSAL Detail specialists. CSM is frozen; shared sources are live, not one historical snapshot.

Managed-model equality is unverified. Compare complete setups, not claim the data design alone caused differences. Do not reuse V1 results as V2 evidence.

## Current simple workflow

Files 26–39 map to cells 1–14. Revision: `v2_simple_runner_1`. Label: `sales_ai_v2_first12_simple_01`.

Manual review/control flags, request-schema flags and both enabling switches are removed. Do not reintroduce flag-setting instructions. Cell 7 checks preparation and source versions, then saves or resumes `v2-benchmark-simple-evidence.json`. Preserve the older `v2-benchmark-evidence.json` untouched.

Both request formats are already `input`, matching observed endpoint Python examples. Cell 8 checks Ready endpoints without OpenAPI discovery. Readiness alone does not prove successful inference.

Local regression and synthetic scoring tests passed; the revised notebook has not been run in Databricks. Earlier reference preparation passed. No verified V2 benchmark results are claimed.

## Start with one pair, retain all 41

Guide me through these steps, waiting for my output after each cell:

1. Confirm the revision from the code I supply. Ask me to run cells 1–6 individually, stopping at the first error. Help check reference logic with `show_reference`; passing preparation is not business verification.
2. Ask me to run cell 7, then cells 8–11. Diagnose the exact error and line if something fails; do not suggest deleting evidence or bypassing checks.
3. Ask me to run cell 12 once with `MAX_TRIALS_THIS_RUN = 2`: one question through both agents. The notebook makes those requests, not Copilot Chat. Then guide me through cell 13, `show_trial` and `record_answer` using actual returned rows. Detailed review is optional.
4. Ask me to run cell 14. Continue one pair at a time, reusing saved trials. Never suggest resending a request whose outcome is uncertain without investigating its saved record.

The full target remains all **41 IDs and unchanged question wording**. Current code supports only **1–7, 15, 18, 20, 23 and 27**: C01–C07, D01, D04, D06, D09 and R01. Three repetitions per agent make **72 trials**, including the first pair.

Once this works, help me extend the same notebook for the remaining 29 by supplying one change at a time. Changing `QUESTION_IDS` alone is insufficient. Keep a simple coverage list with support, reference, execution and pending status. Use a separate checkpoint for the expanded plan; preserve first-batch evidence.

All 41 would mean **246 question-level evaluations**, plus extra message turns for question 30. Its two messages must share context, reset for each arm/repetition. Question 28 must remain ambiguous. Limitation and action questions test boundaries, not permission to build features or perform actions.

## Keep evidence honest

The notebook must send tested agents only exact prompts and agreed common context, never reference answers, reference SQL or scoring notes. Use full first-12 `PROMPTS`, including precision and sorting. Define missing contracts before observing answers.

Record only rows and SQL actually returned. Missing evidence stays unavailable or incomplete. Keep NULL separate from zero; do not double-count commitment across TCRs. Preserve stored flags, source-local identities and comparable sources/settings. Changed or unverifiable conditions make comparisons inconclusive.

Report numerical correctness, guardrails, pending tests, repeatability, SQL and response time separately. Keep customer identifiers and checkpoint contents out of Git.

Production, enrichment, threshold calibration and swap scoring stay unchanged. Ask before suggesting new access, business decisions or expanded actions. Start by asking which cell I last completed and for its output. Do not assume a successful run or start by generating more code.
