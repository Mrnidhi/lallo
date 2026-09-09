# Sales AI V2: run the notebook manually

Use the existing personal **09-sales-ai-v2-benchmark** notebook. Keep the completed build notebook unchanged. All Databricks work stays in the approved office session.

[Project summary](PROJECT_SUMMARY.md) explains the goal and current position.

## What changed

The same 14 cells now have shorter comments, clearer output and practical next steps. Cell 7 lists missing setup items together. Cell 14 distinguishes saving being off from a missing result file.

Questions, calculations, scoring rules and the 72-run plan are unchanged. Internal field names such as `REVIEW` are retained for compatibility with saved experiments. No unfinished check is automatically marked complete.

## Copy the files

Open each file and use **Copy raw file**. Replace only its matching notebook cell. Preserve any deliberate settings already entered in cell 2. Do not use **Run all**.

| Cell | File | What you do |
|---:|---|---|
| 1 | [26_imports.py](26_imports.py) | Load imports. |
| 2 | [27_settings.py](27_settings.py) | Set the existing sources and test settings. |
| 3 | [28_source_checks.py](28_source_checks.py) | Check source columns, keys and versions. |
| 4 | [29_booking_ground_truth.py](29_booking_ground_truth.py) | Calculate and cross-check booking answers. |
| 5 | [30_shared_ground_truth.py](30_shared_ground_truth.py) | Calculate finance, case and Daily Outlook answers. |
| 6 | [31_questions_and_review.py](31_questions_and_review.py) | Inspect the exact questions and reference answers. |
| 7 | [32_freeze_and_checkpoint.py](32_freeze_and_checkpoint.py) | Check the setup and save or load its checkpoint. |
| 8 | [33_endpoint_adapter.py](33_endpoint_adapter.py) | Inspect both agent connections. |
| 9 | [34_paired_runner.py](34_paired_runner.py) | Load the paired runner. |
| 10 | [35_scoring_helpers.py](35_scoring_helpers.py) | Load the answer comparisons. |
| 11 | [36_scoring_self_tests.py](36_scoring_self_tests.py) | Test the scorer with synthetic examples. |
| 12 | [37_run_approved_batch.py](37_run_approved_batch.py) | Send the selected pairs when enabled. |
| 13 | [38_review_recorded_answers.py](38_review_recorded_answers.py) | Check saved responses and their original SQL. |
| 14 | [39_results_and_handoff.py](39_results_and_handoff.py) | Show the before-and-after report. |

## Run in five stages

### 1. Prepare the answers: cells 1–6

In a fresh session, run these cells individually and stop on a failure. Start with `ENABLE_EVIDENCE_SAVE = False` and `ENABLE_AGENT_RUNS = False`.

Cell 2 initializes settings. Do not rerun it unchanged later: it resets the flags and other values. For a small change, use an individual assignment in a temporary Python cell at the bottom of the notebook.

After cell 6, use `show_reference("C01")`. Repeat for C02–C07, D01, D04, D06, D09 and R01. Check the question, filters, calculation, row level, sorting and missing values against the specifications. These outputs stay in the personal workspace.

### 2. Save the setup: cell 7

Record completed checks in the existing `REVIEW` and `CONTROL_EVIDENCE` fields. Record the actual checker, notes, cell 6 fingerprint and when the current agent settings were checked.

For example, **only after checking sorting and rounding**, an individual assignment is:

```python
REVIEW["ordering_and_precision"] = True
```

Make other changes individually, based on completed work. Preserve those deliberate values in cell 2 for a future session, without rerunning all its defaults now. [The setup guide](CHECK_CELL_7.md) explains where each check comes from.

Cell 7 lists all missing entries before it attempts to save. Once the checks are complete:

```python
ENABLE_EVIDENCE_SAVE = True
ENABLE_AGENT_RUNS = False
```

Run cell 7. It saves or loads the personal checkpoint and verifies it can be read back. If an existing checkpoint has different settings, preserve it and investigate. Do not delete it or rename the experiment to clear the error.

When resuming an existing checkpoint, preserve its original `REVIEW` and `CONTROL_EVIDENCE` values, including notes and timestamps. Filling them again can create a different test identity.

### 3. Check the connections and scorer: cells 8–11

Run cell 8. Inspect each endpoint's schema, or its existing **Query / Get code** example when the schema is unavailable. No question is sent by this cell.

After the last run of cell 8, set each entry in `REQUEST_CONTRACT` to the format actually shown for that endpoint: `input` or `messages`. Set its `REQUEST_SCHEMA_REVIEWED` entry to `True` only after confirming it. Do not guess the format. Rerunning cell 8 can clear these settings.

Run cells 9, 10 and 11. They load helpers and test the scorer without sending agent questions.

### 4. Run one pair, then continue: cells 12–13

When the setup, connections and scorer checks are complete:

```python
MAX_TRIALS_THIS_RUN = 2
ENABLE_AGENT_RUNS = True
```

Run cell 12 once, then run cell 13 to load its helper functions. In the temporary cell, inspect the responses with `show_trial("C01", "A", 1)` and `show_trial("C01", "B", 1)`. Check that the response and genuine SQL evidence are available before increasing the batch.

Use cell 13's template to record the actual returned values, source usage and SQL evidence. Never copy expected answers into the returned-answer fields. Missing SQL or timing must remain unavailable.

Repeat cell 12 to continue the same plan, then check the new responses. The first pair is included in the **72 planned runs**. Existing recorded trials are not submitted again. If a timeout or uncertain request occurs, keep its evidence and investigate before continuing.

### 5. Read the comparison: cell 14

Cell 14 reports saved responses. It does not ask new questions. Unrun or unchecked results stay incomplete, not correct.

Use `show_sql_example("C01")` for a before-and-after SQL example when genuine SQL was captured. Compare correctness, consistency and speed together; a shorter query is not automatically a better answer.

## Keep the test comparable

Keep the sources, questions, filters, instructions and endpoint settings unchanged during the experiment. Source and configuration checks remain active. A changed or unverifiable source makes the affected comparison inconclusive.

This is a managed-agent comparison, not proof of identical underlying models or an exact production replica. Enrichment, threshold changes and swap scoring remain outside this batch.

Local checks passed. The revised cells still need execution in Databricks; they do not establish new agent results. Keep generated answers and checkpoint files out of this Git repository.
