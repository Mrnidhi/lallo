# Sales AI V2: a simpler manual run

Use the existing **09-sales-ai-v2-benchmark** notebook and its same 14 cells. Replace each cell with the matching file below. Keep the completed build notebook unchanged. Use only the approved office session. Do not use **Run all**.

[Project summary](PROJECT_SUMMARY.md) · [All 41 questions](question_bank.md) · [Diagrams](OBSIDIAN_PRODUCTION_AND_V2.md) · [Copilot Chat instructions](OFFICE_COPILOT_HANDOFF.md)

Copilot Chat is a code helper: it suggests changes and explains outputs. You paste and run the cells. It is separate from the two Databricks agents being tested.

## What changed

**If cell 12 says “Request completion is uncertain”:** do not rerun it or use Run all. Copy [check_cell_12.py](troubleshooting/check_cell_12.py) into a temporary Python cell at the bottom of the existing notebook. Run only that cell and share its status output. It reads the checkpoint without sending a request, changing evidence or printing answer rows. This diagnostic is not a fix or a replacement for cell 12.

This revision removes manual review flags, enabling switches and request-schema setup. Cell 7 checks preparation and source versions automatically, then saves or resumes a separate checkpoint: `v2-benchmark-simple-evidence.json`. It leaves `v2-benchmark-evidence.json` untouched.

Code version: `v2_simple_runner_1`. Experiment: `sales_ai_v2_first12_simple_01`. Both request formats are set to `input`, matching observed endpoint Python examples. Cell 8 checks Ready endpoints without OpenAPI discovery.

Questions, reference calculations, ordering, precision and scoring intent are unchanged. Automatic checks do not establish business correctness.

## Replace the matching cells

Use **Copy raw file**. Preserve deliberately selected source settings before replacing cell 2.

| Cell | File | Purpose |
|---:|---|---|
| 1 | [26_imports.py](26_imports.py) | Imports |
| 2 | [27_settings.py](27_settings.py) | Sources and settings |
| 3 | [28_source_checks.py](28_source_checks.py) | Source checks |
| 4 | [29_booking_ground_truth.py](29_booking_ground_truth.py) | Booking reference answers |
| 5 | [30_shared_ground_truth.py](30_shared_ground_truth.py) | Shared-domain reference answers |
| 6 | [31_questions_and_review.py](31_questions_and_review.py) | Exact prompts and references |
| 7 | [32_freeze_and_checkpoint.py](32_freeze_and_checkpoint.py) | Check and save the setup |
| 8 | [33_endpoint_adapter.py](33_endpoint_adapter.py) | Check endpoints |
| 9 | [34_paired_runner.py](34_paired_runner.py) | Load runner |
| 10 | [35_scoring_helpers.py](35_scoring_helpers.py) | Load scoring |
| 11 | [36_scoring_self_tests.py](36_scoring_self_tests.py) | Synthetic scorer checks |
| 12 | [37_run_approved_batch.py](37_run_approved_batch.py) | Send one pair |
| 13 | [38_review_recorded_answers.py](38_review_recorded_answers.py) | Inspect and record returned answers |
| 14 | [39_results_and_handoff.py](39_results_and_handoff.py) | Show report |

Existing filenames are retained; no additional notebook or framework is needed.

## Run, inspect, continue

1. Run **cells 1–6 individually**, stopping at the first error. Cell 2 initializes settings; do not rerun its defaults casually. After cell 6, use `show_reference("C01")` to inspect a prompt, reference rows and SQL. Check the reference logic; keep those rows private.
2. Run **cell 7**. It validates preparation, checks sources and saves or resumes the simple checkpoint. No manual approval assignments are needed. If the saved setup differs, preserve the file and investigate; do not delete evidence. See [cell 7 help](CHECK_CELL_7.md).
3. Run **cells 8–11** individually. They check connections and load/test helpers without sending benchmark questions.
4. Manually run **cell 12 once**. It sends at most **two trials: one question through both agents**. Run cell 13, then inspect `show_trial("C01", "A", 1)` and `show_trial("C01", "B", 1)`. Use its `record_answer` template for actual returned rows and notes. Detailed review is optional. Never substitute reference rows or invented SQL.
5. Run **cell 14** to see the saved comparison. Missing SQL, timing or unchecked answers remain unavailable or incomplete. Repeat cell 12 to continue one pair at a time; saved trials are reused. Investigate uncertain requests before resending anything.

## Full scope and limits

All **41 questions** remain the target. This runner supports only the unchanged first **12**: **1–7, 15, 18, 20, 23 and 27**. Three repetitions per agent make **72 trials**, including the first pair. The remaining 29 need execution and scoring support; changing the question list alone is insufficient. Question 30 needs two-message handling.

Keep both arms’ full prompts, sources and settings comparable. Never send reference answers or scoring notes to tested agents. This compares managed setups, not proven identical underlying models. Production, enrichment, thresholds and swap scoring stay unchanged.

Local regression and synthetic scoring tests passed. The latest supplied screenshot shows cell 11 passed its 40 scorer checks, but cell 12 could not confirm request completion. The underlying error and successful benchmark results are not yet verified. Keep generated answers and checkpoint files out of Git.
