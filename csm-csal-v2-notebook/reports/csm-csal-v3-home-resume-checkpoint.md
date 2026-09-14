# CSM/CSAL V3 home resume checkpoint

## Current mode

Office support is through Git only. Resume Windows VM work only after the user says they are home. Continue the existing Word report at Desktop\temp analysis\csm csal v3 grain analysis report.docx.

## Latest requirement

Every evidence section needs the exact question, production main-agent response screenshot, matching Databricks SQL code screenshot, SQL result screenshot and an explanation below them. The explanation must identify observations and unresolved business semantics.

Replace the manually typed section-4 table with genuine Databricks diagnostic output. Use the same Word file.

## Method correction

The earlier MAX-based totals and "ten admitted failures" labels were too strong. Use [the corrected grain review](../grain-review/README.md) and [eight copy-ready cells](../grain-review/COPY_CELLS.md).

No expected number of failures is required. Candidate grains need null-aware consistency, completeness and identity checks. Even a consistent candidate requires verified business grain and additivity. A raw-sum numerical match alone does not prove the agent's computation or causal mechanism.

## Resume sequence

1. Review the office run outputs from the new notebook and record the pinned source version.
2. Reuse an existing screenshot only if its period, source version, metric and meaning match the revised evidence standard.
3. Collect code and output screenshots for each topic using cell 7.
4. Preserve blockers, exclusions and unresolved results.
5. Verify source/filters and the production agent's SQL or tool trace where available.
6. Revise explanations beneath the screenshot pairs.
7. Replace the manual summary table with genuine Databricks diagnostic output.
8. Save and visually review the same Word report.

Detailed questions, filenames, screenshot instructions, reporting language and the V3 plan are in [the report runbook](csm-csal-v3-report-completion-runbook.md).

## Historical evidence

August 2026 Delta v80 had 28,671 rows and 79 columns in the earlier structural sample. Delta v86 was used for later numerical captures. These are historical observations; neither version is assumed current. Old candidate totals are not an automatically approved reference for current production answers.

Known saved SQL images include sql-monthly-totals-v86.jpeg, sql-monthly-confirmed-v86-crop.png and sql-booking-totals-v86.jpeg. Preserve them with their actual provenance, but reassess captions and conclusions under the revised method.

No source rebuild or agent retest is required just to edit the Word layout. If new evidence is needed, use version-pinned read-only queries in the VM after access resumes.
