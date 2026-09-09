# Cell 7: check the current error

Use the existing **09-sales-ai-v2-benchmark** notebook. Do not create another notebook or use **Run all**.

The simple revision uses `v2_simple_runner_1`. Cell 7 checks completed preparation and current source versions, then saves or resumes `v2-benchmark-simple-evidence.json`. There are no review flags or saving/running switches to turn on.

## If it stops

Read the exact error and failing line; a line number alone is not enough.

| Error concerns | Next step |
|---|---|
| Missing preparation or changed inputs | Find the first failed cell among 3–6. Correct that cause and rerun affected preparation in order. After a session restart, run cells 1–6 individually. |
| Source identity, version, columns or timezone | Check the named source or setting in the approved office session. Do not bypass the check or mix changed data into an existing comparison. |
| Existing checkpoint differs | Preserve the file. Check which settings, prompts or source versions changed before choosing a deliberate new experiment. |
| Saving, path or read-back | Check the exact configured workspace location and access. Do not disable persistence or delete the checkpoint to continue. |
| An old review flag or switch | Confirm matching cells 1–14 were replaced from the same simple revision. Do not follow older flag-setting instructions. |

The older `v2-benchmark-evidence.json` is separate and must remain untouched. The obsolete flag diagnostic has been removed from this pack; its earlier version remains in Git history.

After cell 6, `show_reference("C01")` displays the exact prompt, reference rows and calculation. Successful preparation does not by itself verify the business interpretation.

If help is needed, share the exact error, failing line and code version, with private details removed. Keep customer rows, credentials, reference outputs and saved evidence out of Git.

After cell 7 succeeds, run cells 8–11 individually. **Cell 12 sends one A/B pair when manually run.** Cell 14 only reports saved results; a successful setup is not a benchmark result.
