# Continue the Sales AI V2 work with me

I'm continuing an existing CSM/CSAL agent comparison. Please help me finish it using the work already saved, not start another redesign. I will copy the code into my personal Databricks notebook and run it myself. Stay in this chat and help me one step at a time.

Read these files first. If you cannot open a file, tell me which one to attach. Do not assume you have read the repository just because I provided a link.

- `PROJECT_SUMMARY.md`: why we started and what is built.
- `README.md`: the current notebook cells and manual run order.
- `OBSIDIAN_PRODUCTION_AND_V2.md`: the documented production pattern and our personal build.
- `question_bank.md`: all 41 questions, their test IDs, business purpose and support limits.
- The relevant Python cells, especially settings, reference answers, checkpoint, runner and scorer.

Repository: [Sales AI V2 notebook and handoff](https://github.com/Mrnidhi/lallo/tree/main/csm-csal-v2-notebook).

The specification labels in the question bank refer to documents retained in the approved workspace. Those source documents are not included in this repository. Ask for the relevant document if a business rule cannot be established from the supplied evidence.

## What we are trying to prove

Simple business questions were sometimes producing long SQL or incorrect answers. We built an alternative CSM structure to see whether clearer data makes the agents more accurate and consistent, and whether it affects response time.

Do not assume a wide table is bad or that fact and dimension tables must be faster. We need measured results. Production stays unchanged.

The personal model has seven dimension tables, three fact tables and a prepared booking view. The dimensions hold labels; the facts separate booking, commitment and allocation figures. Saved relationship and measure checks passed. This is a CSM proof of concept, not a completed redesign of all Gold domains.

Our main agents are:

- Before: `sales-ai-wide-baseline-v2`, using `CSM Wide Baseline V2`.
- After: `sales-ai-booking-scope-v2`, using `CSM Booking Scope V2`.

Both also use the same four specialists: `Sales Finance V2`, `Sales Cases V2`, `Sales Workspace V2` and `CSAL Detail V2`. Only the CSM data-access path differs. The CSM source is frozen; the shared sources are live. Their data must not be described as one common historical snapshot.

Databricks manages the underlying models, and their equality is not verified. Compare the complete test setups without claiming the data redesign alone caused a difference. The smaller V1 test improved accuracy but was not faster. Do not reuse its answers, hashes or accuracy numbers as V2 evidence.

## Where we are now

Use the existing personal notebook `09-sales-ai-v2-benchmark`. The code files numbered 26–39 correspond to its cells 1–14. Leave the completed build notebook unchanged.

The latest code has clearer comments and messages. Local tests passed, but that does not prove successful execution in Databricks. Reference-answer preparation previously passed; the current manual run stopped at cell 7. We still need its exact error or the new missing-item list. There are no verified V2 benchmark results yet.

Cell 7 checks the setup and saves the experiment. Cell 12 sends test questions. Cell 13 loads helpers for checking saved answers and their SQL. Cell 14 reports the saved results. A setup failure is not evidence of a production data defect.

Cell 2 initializes settings and can reset them when rerun. Help me make individual changes in a temporary cell instead of repeatedly running all its defaults. Keep deliberate settings saved for a later session. Do not mark unfinished checks complete just to get past an error.

## Use all 41 questions

The target is now the complete 41-question bank. Do not finish with only the first 12 and describe that as the full benchmark.

The current notebook supports a first batch of 12: questions **1–7, 15, 18, 20, 23 and 27**, which map to **C01–C07, D01, D04, D06, D09 and R01**. The other 29 still need suitable execution and scoring support. Expanding `QUESTION_IDS` alone will not make the runner ready.

Keep all 41 question numbers and IDs. Create a coverage checklist in the existing notebook, with one row per question showing its business purpose, required data, expected row level, support status, reference-answer status, execution status and remaining issue.

Separate three situations:

1. **Numerical retrieval:** independently establish the expected rows, calculations, sorting and missing-value behavior before scoring the agent.
2. **Clarification or limitation questions:** define what an honest, correct response should explain. Do not require fabricated numbers or call a correct refusal a failed numerical answer.
3. **Unresolved tests:** keep an explicit pending status and reason. Missing evidence is neither a pass nor a zero.

Question 28 deliberately leaves the meaning of fulfillment unclear. Do not fill in those omissions. Question 30 is a two-message conversation; the second message must retain the first message's context. Reset that conversation for each repetition and each main agent. The current fresh-request runner needs explicit support for this before it can test that question properly.

Questions 37–40 test limits around swaps, thresholds, history and actions. They are not instructions to build those features, change rules, send anything or reserve capacity. Follow the question bank's specific support notes for the other conditional questions too.

For three repetitions on both agents, the full plan contains **246 question-level evaluations**. Question 30 requires extra message turns, and pending tests must remain visible rather than being reported as completed. Keep the current 72-run first-batch results as a separate, clearly labelled subset.

Use the first 12 to establish that the connection, evidence capture and scoring work. Then extend the same notebook to cover the remaining 29, checking each test's contract before running it. Do not create new tables or agents merely to make a test pass.

## Keep the comparison fair

For the first 12, use the notebook's exact `PROMPTS`, including the sorting and precision notes. The numbered questions alone omit some of that detail. For the other questions, define any missing result contract before observing either agent's answers, and use it identically in both setups.

Use the same verified dates, identities, instructions, warehouse and non-CSM sources. Actual customer and booking identifiers stay inside the approved workspace. Do not publish them to GitHub. Do not assume that a matching customer or representative name in two domains proves one shared identity.

Give the tested agents only the test question and agreed common context. Do not feed them reference answers, reference SQL or scoring notes. Check expected answers independently against documented business logic and underlying data, not solely against the after-view or another LLM's answer.

Keep NULL different from zero. Keep booking amounts at customer + agreement + week + service + TCR level, and reviewed commitment once at customer + agreement + week + service level. Do not sum that repeated commitment across TCR rows or average percentages. Preserve current flags and formulas; no new thresholds or probability claims.

If the data or endpoint settings change, or cannot be verified, mark the affected comparison inconclusive. Do not silently mix snapshots. The current code measures client response time; SQL execution time is a separate measure and may be unavailable.

## Help me finish in this order

1. Ask me for cell 7's exact error or setup list and confirm which code version is pasted. Explain the cause before giving a correction. Do not assume the line number alone identifies the problem.
2. Help complete the remaining reference and setup checks, then save or load the personal checkpoint. Preserve existing notes, timestamps and trial records when resuming.
3. Inspect the actual request format for each endpoint. If the schema API is unavailable, use its existing Query/Get code example. Do not try guessed formats or infer that a Ready endpoint accepts any payload.
4. Run one A/B pair only after the setup checks pass. Load cell 13's helpers and inspect both original responses and actual SQL evidence before increasing the batch.
5. Complete the first 12-question subset. Then extend the reference contracts, execution plan, multi-turn handling, scoring and report for all 41. Replace hard-coded 72-run and 12-question assumptions consistently and test the changes with synthetic examples first.
6. Do not append a 41-question plan to an existing 12-question checkpoint. Preserve the original evidence and use a clearly separate personal checkpoint for the expanded plan. Update and check its exact allowed location deliberately; do not bypass the path checks or delete evidence to resolve a mismatch.
7. Present a before-and-after report covering all 41 IDs: numerical correctness, clarification/guardrail results, pending tests, consistency, SQL correctness and complexity, row-level correctness, response time and available SQL duration. Report these categories separately rather than hiding them in one accuracy percentage.

Repeated runs must reuse saved trials. An uncertain timeout may already have reached the server, so do not resend it automatically. Source checks, checkpoint identity checks and single-runner locks must stay effective. Code being safe to rerun does not mean a server request is guaranteed to execute exactly once.

## How I want your help

Keep the explanation short and practical. Tell me which cell to open, what the issue means and what result to expect. If a replacement is needed, give me the complete replacement cell, not scattered edits. Keep imports in cell 1 and comments brief and useful. Use the existing files and directory.

Do not write to production, edit someone else's notebook, change UC functions or rebuild the model. Work only on my personal notebook and its test evidence. Keep enrichment, historical threshold calibration and swap scoring parked.

If you need a business decision, new access, a changed test definition or an action outside this scope, stop and explain the choice in plain English. Otherwise, continue with the next safe step. Do not invent results, give unsupported completion percentages or say a notebook ran unless I provided the output or you actually observed it.

Start by summarizing the current position in five short lines. Then ask me for the latest cell 7 output. Do not start a new project or submit all 41 questions immediately.
