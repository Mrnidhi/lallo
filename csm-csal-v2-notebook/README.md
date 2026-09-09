# Sales AI V2 benchmark cells

Use the existing personal notebook **09-sales-ai-v2-benchmark**. Each Python file is one cell. File numbers 26–39 become notebook cells 1–14. Keep **08-sales-ai-v2-master-poc** unchanged.

## Paste order

| Cell | File | Purpose |
|---:|---|---|
| 1 | [26_imports.py](26_imports.py) | Imports |
| 2 | [27_settings.py](27_settings.py) | Sources and review gates |
| 3 | [28_source_checks.py](28_source_checks.py) | Read-only source checks |
| 4 | [29_booking_ground_truth.py](29_booking_ground_truth.py) | Booking reference answers, including the SQL-string fix |
| 5 | [30_shared_ground_truth.py](30_shared_ground_truth.py) | Finance, cases and Daily Outlook reference answers |
| 6 | [31_questions_and_review.py](31_questions_and_review.py) | Exact questions and review fingerprint |
| 7 | [32_freeze_and_checkpoint.py](32_freeze_and_checkpoint.py) | Approved evidence checkpoint |
| 8 | [33_endpoint_adapter.py](33_endpoint_adapter.py) | Verify endpoint request format |
| 9 | [34_paired_runner.py](34_paired_runner.py) | Define the restart-safe runner |
| 10 | [35_scoring_helpers.py](35_scoring_helpers.py) | Answer scoring helpers |
| 11 | [36_scoring_self_tests.py](36_scoring_self_tests.py) | Synthetic scoring tests |
| 12 | [37_run_approved_batch.py](37_run_approved_batch.py) | Run approved A/B trials |
| 13 | [38_review_recorded_answers.py](38_review_recorded_answers.py) | Review original answers and SQL evidence |
| 14 | [39_results_and_handoff.py](39_results_and_handoff.py) | Before-and-after results |

## Start here

1. Open each file in the office browser. Use **Copy raw file** to copy code only, then replace the matching personal notebook cell. Preserve any deliberately reviewed personal settings. Use this updated pack together; do not mix older helpers with these cells.
2. Keep `ENABLE_EVIDENCE_SAVE` and `ENABLE_AGENT_RUNS` set to `False`. Run cells **1–6 individually, in order**. Do not use Run all. Stop on any failure.
3. Review the reference SQL, fixtures, exact questions and answers shown by cell 6. Passing checks alone is not business approval. Record the displayed `DRAFT_REVIEW_SHA256` only after reviewing that draft.
4. Complete the review/control fields in cell 2 before enabling evidence saving and running cell 7. Verify the real endpoint schemas with cell 8 before setting either request format as reviewed.
5. Run cells 9–11. Start with one approved A/B pair using `MAX_TRIALS_THIS_RUN = 2`. Review both recorded responses before continuing the batch.

This batch contains **12 questions × 2 existing agents × 3 repetitions = 72 trials**. It does not rebuild tables, views or agents. Production remains read-only. Enrichment, threshold changes and swap scoring are outside this batch.

## Rerun rules

Completed trials are reused, not sent again. A timeout may already have reached the server; reconcile the recorded request before considering another attempt. Do not delete evidence or clear a gate to force a rerun. Changed inputs or reference answers require a fresh review.

Local regression checks passed. Live Spark compatibility, endpoint format, evidence-file operations and agent results still need validation in the notebook. Keep generated answers and evidence in the personal workspace, not in this repository.
