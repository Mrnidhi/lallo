# CSM/CSAL V3 Home Resume Checkpoint

## Working mode until the user returns home

- Do not open or operate the Windows VM.
- Provide office support only through files committed to `Mrnidhi/lallo`.
- Do not connect the personal Mac directly to Databricks or any OOCL system.
- Keep production read-only.

## Unfinished report task to resume at home

Continue editing the existing Word report in the VM:

`Desktop\temp analysis\csm csal v3 grain analysis report.docx`

Do not create a second Word report.

The user wants every one of the ten evidence sections to follow this order:

1. Evidence number and metric name
2. Exact natural-language question
3. Production-main-agent answer screenshot
4. Matching Databricks SQL code and result screenshot
5. A short explanation below the screenshots covering:
   - what the production agent returned
   - what the read-only SQL returned at the validated grain
   - the numeric difference
   - which lower-level rows repeated the value
   - why that repetition caused the direct wide-table sum to be incorrect

The Databricks screenshot must visibly include the SQL code and its result. It must be a genuine Databricks capture, not a recreated Word table.

## Evidence scope

- Agent evidence: existing production main Sales AI agent only
- Source: `dev.sales_ai_assistant_gold.csm_csal_summary`
- Period: August 2026
- Live source state: Delta version 86
- Live source timestamp: 13 September 2026 at 11:30:55 UTC
- Structural reference: August 2026 at Delta version 80, 28,671 rows and 79 columns

Do not compare a version-86 agent answer with a version-80 SQL total.

## Validated grains for the ten live cases

Monthly measures must be counted once for:

`month + customer + sales_rep + agreement + service`

Booking measures must be counted once for:

`customer + agreement + week_num + service + tcr`

## Ten admitted live comparisons

| Evidence | Metric | Production answer and raw wide sum | Correct-grain total | Difference |
|---|---|---:|---:|---:|
| 1 | Monthly booked TEU | 1,549,331 | 256,071 | 1,293,260 |
| 2 | Monthly cancelled TEU | 378,095 | 63,262 | 314,833 |
| 3 | Monthly rejected TEU | 265,931 | 47,660 | 218,271 |
| 4 | Monthly confirmed TEU | 848,446 | 135,399 | 713,047 |
| 5 | Booked TEU | 256,714 | 248,607 | 8,107 |
| 6 | Confirmed TEU | 135,802 | 131,114 | 4,688 |
| 7 | Cancelled TEU | 63,433 | 61,325 | 2,108 |
| 8 | Rejected TEU | 47,711 | 46,640 | 1,071 |
| 9 | No-show TEU | 8,804 | 8,608 | 196 |
| 10 | Terminated TEU | 818 | 780 | 38 |

## Exact questions already used

1. For August 2026, what is the total monthly booked TEU?
2. For August 2026, what is the total monthly cancelled TEU?
3. For August 2026, what is the total monthly rejected TEU?
4. For August 2026, what is the total monthly confirmed TEU?
5. For August 2026, what is the total booked TEU?
6. For August 2026, what is the total confirmed TEU?
7. For August 2026, what is the total cancelled TEU?
8. For August 2026, what is the total rejected TEU?
9. For August 2026, what is the total no-show TEU?
10. For August 2026, what is the total terminated TEU?

## Existing VM evidence folder

Use the files already stored in:

`Desktop\temp analysis`

Known existing SQL output files include:

- `sql-monthly-totals-v86.jpeg`
- `sql-monthly-confirmed-v86-crop.png`
- `sql-booking-totals-v86.jpeg`

Known production-agent screenshot names are documented in the completion runbook.

## Pending work when VM access resumes

1. Run or display one read-only SQL check for each evidence case.
2. Capture ten Databricks screenshots, one for each evidence, with both code and result visible.
3. Name the screenshots consistently, for example:
   - `E01-sql-monthly-booked-v86.png`
   - `E02-sql-monthly-cancelled-v86.png`
   - `E03-sql-monthly-rejected-v86.png`
   - `E04-sql-monthly-confirmed-v86.png`
   - `E05-sql-booked-v86.png`
   - `E06-sql-confirmed-v86.png`
   - `E07-sql-cancelled-v86.png`
   - `E08-sql-rejected-v86.png`
   - `E09-sql-no-show-v86.png`
   - `E10-sql-terminated-v86.png`
4. Update all ten evidence sections in the same Word report.
5. Place the explanation after the SQL screenshot, as requested.
6. Replace the manually formatted section-4 comparison table with genuine Databricks result output.
7. Save the same Word document.
8. Reopen and visually review every screenshot page for readability, cropping, overlap and page breaks.
9. Confirm evidence numbering runs from 1 to 10 and no placeholder images remain.

## Evidence-admission rule

A case belongs in the report only when the production answer matches the direct live wide-table sum and the matching live SQL shows a different total after counting the metric once at its validated grain.

Exclude any case involving a different month, different metric, unsupported answer, rounding-only difference, unexplained mismatch or SQL from another source version.

These ten cases demonstrate a grain risk. They are not a complete production-agent accuracy score.

## Writing rules

- Use professional, neutral language.
- Explain only what the screenshots and SQL prove.
- Do not blame a person or team.
- Do not claim data loss.
- Do not claim the entire production agent is inaccurate.
- Do not claim Arm B or Arm C is production-ready.
- Do not expose credentials, customer-level records or unrelated chats.
- State that production remained read-only.

## Files already available in Git

The full self-contained completion procedure is in:

`csm-csal-v2-notebook/reports/csm-csal-v3-report-completion-runbook.md`

The resume checkpoint should be used together with that runbook. The runbook contains the combined version-86 SQL, exact screenshot requirements, Word-editing steps, quality checks, troubleshooting and remaining V3 plan.

## Resume instruction

When the user says they are home and asks to continue, begin from the ten per-evidence Databricks SQL screenshots. Do not restart the grain analysis, rebuild tables or retest the production agent unless the source version has changed or an existing screenshot fails the evidence-admission rule.
