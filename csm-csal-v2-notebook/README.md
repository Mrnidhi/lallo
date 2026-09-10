# Sales AI V2 CSM benchmark

This folder is the copy point for the personal Databricks notebook. It contains code only. Do not place response rows, credentials or private evidence files in this repository.

## What is being compared

- Agent A uses the personal 78-column wide-table path.
- Agent B uses the personal curated booking-scope view.
- Both receive the same seven CSM questions three times.
- The formal result contains 42 trials: 21 per agent.
- Production is read-only and any production observations stay outside the formal A/B score.

The hard-coded risk flags are tested exactly as stored. This experiment does not validate or change their thresholds.

## Continue in the existing personal notebook

The original preparation, reference, connection and scorer cells must already be loaded. The synthetic scorer check must say that all 40 checks passed.

Copy and run these files in this order, one file per new Python cell:

1. [`43_start_csm_controlled_experiment.py`](43_start_csm_controlled_experiment.py) creates or resumes the separate CSM checkpoint. It sends no questions.
2. [`44_csm_scoped_runner.py`](44_csm_scoped_runner.py) loads the safe runner. It sends no questions by itself.
3. Run `csm_status()` in a small cell to confirm the next pair.
4. Run `run_next_csm_pairs(2)` to ask one question through both personal agents exactly once.
5. [`46_csm_saved_answer_review.py`](46_csm_saved_answer_review.py) provides no-send helpers for reviewing stored answers.
6. Use `preview_csm_answer(question, arm, repetition)` before recording each saved answer.
7. [`45_csm_results_report.py`](45_csm_results_report.py) creates the aggregate CSM report after the existing scoring/report functions are loaded.
8. [`41_aggregate_results_chart.py`](41_aggregate_results_chart.py) renders the final aggregate chart after the report cell.

Do not use Run all. Do not resend an uncertain request. The checkpoint records a request before it is sent and prevents automatic retries or incompatible reruns.

## Why the experiment changed

An unrelated Daily Outlook table refreshed while the older 12-question experiment was running. The CSM tables and booking-view definition did not change. To keep the architecture test controlled, the formal experiment now uses only C01 to C07. Finance, cases, Daily Outlook and cross-domain questions remain separate smoke tests.

## How to describe the result

The primary score is correct answers out of all 21 planned runs per agent. Also report evaluated accuracy, repeat consistency, failures, source and grain evidence, client response time and any original SQL evidence that is actually available.

Any improvement belongs to the complete curated access path, including its narrower view, clearer column names, fixed grain, stored metrics, instructions and routing. It does not prove that facts and dimensions alone caused the change or that production should be redesigned everywhere.

## Supporting files

- [`question_bank.md`](question_bank.md): full 41-question coverage bank
- [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md): project history and current position
- [`OBSIDIAN_PRODUCTION_AND_V2.md`](OBSIDIAN_PRODUCTION_AND_V2.md): production and personal V2 diagrams
- [`OFFICE_COPILOT_HANDOFF.md`](OFFICE_COPILOT_HANDOFF.md): normal Copilot Chat context
