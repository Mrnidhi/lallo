# CSM/CSAL V3 report completion runbook

Revised after reviewing the assumptions in the earlier aggregation queries.

## Start here

Use [the corrected eight-cell notebook guide](../grain-review/COPY_CELLS.md) and [its interpretation instructions](../grain-review/README.md). The earlier unconditional MAX comparisons and requirement to reproduce ten predetermined totals have been superseded. Keep earlier results as historical observations, not verified ground truth.

The existing Word file remains `Desktop\temp analysis\csm csal v3 grain analysis report.docx`. We are providing Git-only office support. VM editing resumes only when the user returns home.

## Run the analysis

1. Create a personal analysis notebook named CSM_CSAL_GRAIN_REVIEW and paste one Python block per cell from the copy guide.
2. Set the exact month in cell 1. Leave SOURCE_VERSION as None for a new current-source review or set a specific version for historical reproduction.
3. Run cells 1–8 in order. Stop on an error; do not use old downstream outputs.
4. Record the pinned version, schema hash, source row count, observed column count and start/end timestamps.
5. Preserve cell 2's null, blank, invalid-value and identity observations.
6. Preserve cell 5's full column inventory, unmapped fields and conflicts across the proposed scopes.
7. Preserve cell 6's complete amount review, including unchanged differences and blocked comparisons.
8. Interpret candidate totals only within their supported population. Missing-key or conflicting groups prevent a complete candidate total. Partial subtotals show exclusions and cannot be compared with a whole-portfolio answer.

## Capture the ten existing topics without selecting only failures

The topic IDs are fixed for traceability; they are not a requirement to find ten errors.

| ID | Cell 7 metric | Question |
|---|---|---|
| E01 | monthly_booked_teu | For August 2026, what is the total monthly booked TEU? |
| E02 | monthly_cancelled_teu | For August 2026, what is the total monthly cancelled TEU? |
| E03 | monthly_rejected_teu | For August 2026, what is the total monthly rejected TEU? |
| E04 | monthly_confirmed_teu | For August 2026, what is the total monthly confirmed TEU? |
| E05 | booked_teu | For August 2026, what is the total booked TEU? |
| E06 | confirmed_teu | For August 2026, what is the total confirmed TEU? |
| E07 | cancelled_teu | For August 2026, what is the total cancelled TEU? |
| E08 | rejected_teu | For August 2026, what is the total rejected TEU? |
| E09 | no_show_teu | For August 2026, what is the total no-show TEU? |
| E10 | terminated_teu | For August 2026, what is the total terminated TEU? |

1. Set EVIDENCE_METRIC in cell 7 to the relevant field.
2. Run cell 7, copy its printed SQL into a personal SQL Editor query and run that SELECT.
3. Capture the SQL code and result. Keep statuses, null counts, missing-key counts and exclusions legible. Use separate images if needed.
4. Save as E01-vNN-code.png and E01-vNN-output.png in Desktop\temp analysis, replacing E01 and NN with the actual topic and version.
5. For concrete repeated-group examples, use SHOW_GROUP_DETAILS = True in cell 7. Keep these source-level details inside the office environment.
6. For an agent comparison, use the existing production main agent. Keep the exact question, full response, conversation/time reference and SQL or UC-function/tool trace if exposed.
7. Use a fresh chat for each predeclared trial. Do not rephrase or retry until the agent fails. Log failed requests, refusals, correct answers and unresolved outcomes as well.
8. Verify the agent's data source, version and filters. Temporal proximity alone does not establish snapshot equality. If the source version is not observable, record that uncertainty.
9. Never pair historical v86 answers with current-version SQL. Historical v80 structural checks and v86 numerical captures remain separately labelled.

## Explain the evidence below each screenshot pair

For each section use this order: question; production-agent answer screenshot; SQL code screenshot; SQL result screenshot; short explanation.

Explain the observed row count and proposed grouping, whether values were constant, which null/key checks passed or blocked the calculation, the raw sum and eligible candidate result, and the exact evidence still needed.

A match to the raw sum does not alone prove which query the agent executed. A lower candidate total does not alone prove that repeated physical rows represent the same business event.

Use one of these conclusions:

- Candidate grouping is consistent in this sample; business identity/grain/additivity remains unverified.
- Candidate grouping has conflicts; complete total withheld.
- Candidate grouping has incomplete keys or values; subtotal is partial.
- Agent result agrees with a separately verified reference.
- Agent result differs from a separately verified reference; cause not yet established.
- Grain-related error demonstrated by aligned data, a validated reference and the agent's actual query/tool trace.
- Unresolved because source alignment, identity rules, formula or trace is unavailable.

Do not use the last failure label without the supporting evidence. The analysis is allowed to find that production handles a metric correctly.

## Replace the section-4 table

Replace the manually typed comparison table with genuine Databricks diagnostic output. Captions must identify candidate results and exclusions. The full result may require more than one image. Do not retain an old table headed "Correct grain" unless its business reference has actually been independently established.

Use Word Insert > Pictures > This Device, choose In Line with Text and preserve the original aspect ratio. Save the same Word file.

The current request explicitly includes SQL code screenshots in every evidence section, superseding the older instruction to show outputs only.

## Keep the report's story factual

1. Explain the selected source, month and version.
2. Show the observed grains, nulls, key limitations and column coverage.
3. Explain the candidate calculations and what remains unresolved.
4. Show the ten paired topics with all relevant outcomes retained.
5. State what the evidence establishes and what it cannot establish.
6. Finish with the agreed V3 plan and the existing notebook link copied inside the office environment.

Do not label sample constancy, technical key uniqueness or a successful 79-column round trip as proof that every business metric is correct. A round trip establishes information preservation for that tested sample, not semantic correctness.

## V3 plan to include

Arm A remains the existing production tables and agent. Arm B uses all six agreed Gold sources to build personal facts and dimensions, then business views for Genie. Arm C uses CSM/CSAL as the source for actual personal normalized tables with verified primary and foreign keys, connected directly to Genie.

The six Arm B sources are csm_csal_summary, fincon_issues, sales_ai_roster, sales_ai_case_ledger, sales_ai_case_issues and tea_deliverables.

Reuse compatible V2 work, confirm identities and producer logic, validate every mapping and join, preserve all source information, and resolve missing-value rules before comparing agents. Give the personal agents equivalent preparation, separate tuning and scored questions, freeze configurations, and run the same applicable questions three times. Compare accuracy, consistency, complexity and timing without presuming which implementation wins. Differences in source freshness, tools and production configuration must remain visible.

## Final review

- Confirm all code and output images are readable and captions identify the right topic/version.
- Keep evidence numbering consistent and remove missing-image placeholders.
- Confirm candidate totals are not described as independently verified ground truth.
- Confirm partial subtotals are not compared with full-portfolio agent answers.
- Confirm correct and unresolved results have not been hidden.
- Confirm data preservation is not presented as proof of formula correctness.
- Confirm the production main agent's identity and source alignment are documented.
- Confirm causal claims are supported by trace evidence, or explicitly described as unverified.
- Check every page after saving, including image sizes, overlap, page breaks and notebook hyperlink.
- Preserve production as read-only and save the same Word report.

Screenshots, customer-level records and the Word file stay in the office environment. Git contains only the authorized code copies and documentation.
