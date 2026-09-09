# Cell 7: find the missing review

Use this in your existing personal **09-sales-ai-v2-benchmark** notebook. Do not create another notebook, change production or use **Run all**.

Keep Databricks and agent-setting checks inside your approved office session. If that session is unavailable or logged out, stop rather than switching to another environment.

## 1. Show what is missing

1. In this GitHub folder, open [troubleshooting/check_cell_7.py](troubleshooting/check_cell_7.py).
2. Click **Copy raw file** above the code.
3. In Databricks, add one temporary **Python** cell at the very bottom, after the report cell. This keeps the existing cells in their current order.
4. Paste the code and run **only that temporary cell**.
5. Use the status output to find missing items. If you need help, share it with the original error message and failing code line, with any private details removed. Older copies may raise `AssertionError`; the new setup list raises `RuntimeError`.

The diagnostic reads existing notebook variables only. It does not query tables, call agents, read or save files, or change approvals. It does not print customer rows, names, reviewer notes or credentials.

Do not replace cell 7 with this diagnostic. The revised cell 7 prints its missing setup items together; older copies may show only an assertion. Line numbers can change between versions, so use the actual message and code line.

## 2. Understand the output

| What it shows | Where to check | What to do |
|---|---|---|
| Missing preparation receipt | Outputs of cells 3, 4, 5 and 6 | Find the first failed step. If the session restarted, preparation must be rerun in order. Do not approve a missing result. |
| `business_logic_and_ground_truth` pending | Reference answers and SQL available after cell 6 | Check that the expected answers follow the specifications and source logic, not just an agent's explanation. |
| `source_local_fixtures` pending | The exact prompts and reference answers after cell 6 | Check the selected dates, filters and records. Representatives are selected within each source; matching names do not prove a shared identity. |
| `ordering_and_precision` pending | The method notes included in each prompt | Check sorting, tie-breakers, rounding and missing-value handling. Both agents must receive the same full prompt. |
| `current_agent_controls` or control fields pending | The two personal main-agent settings and their specialist settings | Check matching saved instructions, the same four shared specialists and matching warehouse/settings. Only the CSM specialist should differ. Old reference hashes alone are not a current check. |
| Reviewer or notes missing | `REVIEW` in cell 2 | Record the actual reviewer and a short, factual description of what they checked. |
| Approval fingerprint missing or different | Final output of cell 6 | After reviewing that exact draft, record its fingerprint in `REVIEW["draft_sha256"]`. Do not copy it merely to remove an error. |
| Verification date missing | `CONTROL_EVIDENCE` in cell 2 | Record when the agent settings were actually checked, in UTC. Do not backdate a check. |

`TRUE recorded` means someone set a flag. It does not prove that the review happened. A matching stored fingerprint also does not prove that live sources are unchanged.

## 3. Open the questions and expected answers

After cell 6 succeeds, use the same temporary cell to run:

```python
show_reference("C01")
```

This displays the exact question, its requirement reference, expected level of detail, expected rows and reference SQL. Repeat with **C02, C03, C04, C05, C06, C07, D01, D04, D06, D09 and R01**.

If using an older cell 6, the same helper is named `show_review`. The revised cell keeps both names available.

Review these inside the office notebook. They can contain business data. Do not upload their output, the saved experiment file or customer screenshots to GitHub. Share the diagnostic statuses instead.

## 4. Record the review, then continue

The review fields live in cell 2 under `REVIEW` and `CONTROL_EVIDENCE`. Editing displayed code alone does not change the values already in memory. But rerunning all of cell 2 with its defaults resets approvals and other settings.

Use the missing-item list to update only fields backed by completed checks. Make individual assignments in the temporary cell and preserve those deliberate settings in cell 2. Ask for help if an item is unclear. Do not turn every flag on, auto-fill a completed check from a passing test, or remove assertions.

The model limitation was already accepted: this compares two Databricks-managed setups, not a proven identical underlying model or an exact copy of production.

After the review is genuinely complete, cell 7 can save the approved experiment in the personal workspace. It does not ask agents any questions. Endpoint checks and the first paired test come next; keep agent runs disabled until those checks are ready.

If cell 7 reports a changed source or an existing experiment mismatch, stop and preserve the evidence. Changing review notes or control records can change the experiment identity. Do not delete the saved file or rename the experiment to bypass that check.

Cell 14 now prints **Report not loaded** with a specific reason: saving is disabled, or the configured evidence file is missing. Older copies combine those reasons into **No stored experiment to report**. Neither is a reason to bypass cell 7. Actual comparison results also require recorded agent responses and their checks.
