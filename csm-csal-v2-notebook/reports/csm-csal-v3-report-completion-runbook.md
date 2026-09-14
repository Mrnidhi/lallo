# CSM/CSAL V3 Grain Analysis Report Completion Runbook

## Purpose

Use this runbook to finish the existing CSM/CSAL V3 Word report without needing any additional instructions.

The report demonstrates one specific finding: several business measures in the current wide CSM/CSAL table are repeated across more detailed rows. A direct sum can therefore count the same business value more than once. The report pairs each admitted production-agent answer with a live Databricks result that shows both the direct wide-table total and the total calculated once at the validated business grain.

This is a focused grain-risk analysis. It is not a general accuracy score for the production agent, and it does not authorize any production change.

## Definition of complete

The document is complete only when all of the following are true:

- The existing Word report is used; no replacement report is created.
- Section 4 contains genuine Databricks result output instead of a manually typed comparison table.
- Ten production-main-agent screenshots are present: four monthly measures and six booking measures.
- Every production-agent result is paired with a live SQL result for the same month, metric and source version.
- The structural analysis and the live evidence are clearly separated.
- All captions, explanations, screenshots, page numbers and the notebook reference are readable.
- The final section explains the next V3 actions for Arms B and C without claiming that either design is already production-ready.
- Production remains read-only throughout.

## Working locations inside the Windows VM

Use these existing items:

- Word report: `Desktop\temp analysis\csm csal v3 grain analysis report.docx`
- Evidence folder: `Desktop\temp analysis`
- Databricks notebook: open the existing grain-and-key validation notebook with ID `1001878441092879`
- Production source: `dev.sales_ai_assistant_gold.csm_csal_summary`
- Production agent: use only the existing production main Sales AI agent for the evidence section

Do not upload the Word report, internal links, customer-level rows, credentials or production screenshots to a public repository. The Markdown runbook may be stored in Git because it contains only aggregate evidence and operating instructions.

## Evidence periods that must remain separate

Two related evidence sets appear in the report:

| Evidence use | Period | Source state | Purpose |
|---|---|---|---|
| Structural grain analysis | August 2026 | Delta version 80 | Establish the 79-column source structure and candidate grains using 28,671 rows |
| Live production-agent evidence | August 2026 | Delta version 86, 13 September 2026 at 11:30:55 UTC | Compare production-agent answers with live SQL totals from the same source state |

Never judge a version-86 agent answer against a version-80 SQL total. If the production source refreshes and the agent is tested again, start a new evidence version and rerun every matching SQL calculation.

## Expected evidence files

The evidence folder should contain the following files. Keep an existing file when it is readable and matches the description. Recapture only files that are missing, cropped incorrectly or from the wrong source state.

### Structural analysis

| File | What it must show |
|---|---|
| `source-version-v86.jpeg` | The source table history/result identifying Delta version 86 and its timestamp |
| `02-month-selection.png` | August 2026 selected as a completed month, with 28,671 rows and four reporting weeks |
| `03-candidate-grains.png` | Allocation, booking, commitment, monthly-performance and agreement-context grain counts |
| `4-model-inventory.png` | The proposed dimensions and facts with their primary-key checks |

### Live Databricks totals

| File | What it must show |
|---|---|
| `sql-ten-grain-comparisons-v86.png` | Preferred single result grid containing all ten live comparisons |
| `sql-monthly-totals-v86.jpeg` | Existing output for monthly booked, cancelled and rejected TEU |
| `sql-monthly-confirmed-v86-crop.png` | Existing output for monthly confirmed TEU |
| `sql-booking-totals-v86.jpeg` | Existing output for the six booking-grain measures |

The preferred section-4 replacement is `sql-ten-grain-comparisons-v86.png`. If it cannot be produced, use the three existing genuine Databricks output images in the order listed above. Do not rebuild the comparison as another Word table.

### Production-main-agent answers

| Evidence | File | Exact question |
|---|---|---|
| 1 | `agent-monthly-booked-v86.jpeg` | For August 2026, what is the total monthly booked TEU? |
| 2 | `agent-monthly-cancelled-v86.jpeg` | For August 2026, what is the total monthly cancelled TEU? |
| 3 | `agent-monthly-rejected-v86.jpeg` | For August 2026, what is the total monthly rejected TEU? |
| 4 | `agent-monthly-confirmed-v86.jpeg` | For August 2026, what is the total monthly confirmed TEU? |
| 5 | `agent-booked-v86.jpeg` | For August 2026, what is the total booked TEU? |
| 6 | `agent-confirmed-v86.jpeg` | For August 2026, what is the total confirmed TEU? |
| 7 | `agent-cancelled-v86.jpeg` | For August 2026, what is the total cancelled TEU? |
| 8 | `agent-rejected-v86.jpeg` | For August 2026, what is the total rejected TEU? |
| 9 | `agent-no-show-v86.jpeg` | For August 2026, what is the total no-show TEU? |
| 10 | `agent-terminated-v86.jpeg` | For August 2026, what is the total terminated TEU? |

## Step 1: Confirm the structural evidence

Open the existing grain-and-key validation notebook. Use only completed output cells; do not show notebook code in the report.

### 1.1 Source version screenshot

1. Display the read-only table-history result for `dev.sales_ai_assistant_gold.csm_csal_summary`.
2. Confirm that version 86 and the timestamp are visible.
3. Capture only the Databricks output area and enough interface chrome to identify Databricks.
4. Save the image as `source-version-v86.jpeg` in `Desktop\temp analysis`.

### 1.2 Month-selection screenshot

1. Open the output that profiles source months.
2. Confirm that August 2026 is a completed month.
3. Confirm the selected-month result shows 28,671 rows and four reporting weeks.
4. Capture the output only.
5. Save it as `02-month-selection.png`.

### 1.3 Candidate-grain screenshot

Capture the result that contains these structural counts:

| Business area | Rows at validated grain | Repeated source rows |
|---|---:|---:|
| Allocation | 28,671 | 0 |
| Booking | 28,115 | 556 |
| Commitment | 21,085 | 7,586 |
| Monthly performance | 10,445 | 18,226 |
| Agreement context | 2,368 | 26,303 |

Save it as `03-candidate-grains.png`.

### 1.4 Proposed-model inventory screenshot

Capture the completed output showing:

- Eight candidate dimensions
- Five candidate facts
- Unique and non-null technical primary keys
- No technical-key collisions
- Foreign-key checks with zero orphan rows
- Round-trip reconstruction of all 79 columns and all 28,671 August rows

Save the relevant output as `4-model-inventory.png`.

The report may describe this as a passed one-month design validation. Do not describe it as production deployment or final business approval.

## Step 2: Create the single Databricks comparison output

Open Databricks SQL Editor and create a new query. Run the following read-only SQL exactly as written.

```sql
WITH source_data AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 86
  WHERE month = 'August 2026'
),
monthly_grain AS (
  SELECT
    month,
    customer,
    sales_rep,
    agreement,
    service,
    MAX(monthly_booked_teu) AS booked_teu,
    MAX(monthly_cancelled_teu) AS cancelled_teu,
    MAX(monthly_rejected_teu) AS rejected_teu,
    MAX(monthly_confirmed_teu) AS confirmed_teu
  FROM source_data
  GROUP BY month, customer, sales_rep, agreement, service
),
booking_grain AS (
  SELECT
    customer,
    agreement,
    week_num,
    service,
    tcr,
    MAX(booked_teu) AS booked_teu,
    MAX(confirmed_teu) AS confirmed_teu,
    MAX(cancelled_teu) AS cancelled_teu,
    MAX(rejected_teu) AS rejected_teu,
    MAX(no_show_teu) AS no_show_teu,
    MAX(terminated_teu) AS terminated_teu
  FROM source_data
  GROUP BY customer, agreement, week_num, service, tcr
),
raw_totals AS (
  SELECT
    CAST(ROUND(SUM(monthly_booked_teu), 0) AS BIGINT) AS monthly_booked,
    CAST(ROUND(SUM(monthly_cancelled_teu), 0) AS BIGINT) AS monthly_cancelled,
    CAST(ROUND(SUM(monthly_rejected_teu), 0) AS BIGINT) AS monthly_rejected,
    CAST(ROUND(SUM(monthly_confirmed_teu), 0) AS BIGINT) AS monthly_confirmed,
    CAST(ROUND(SUM(booked_teu), 0) AS BIGINT) AS booking_booked,
    CAST(ROUND(SUM(confirmed_teu), 0) AS BIGINT) AS booking_confirmed,
    CAST(ROUND(SUM(cancelled_teu), 0) AS BIGINT) AS booking_cancelled,
    CAST(ROUND(SUM(rejected_teu), 0) AS BIGINT) AS booking_rejected,
    CAST(ROUND(SUM(no_show_teu), 0) AS BIGINT) AS booking_no_show,
    CAST(ROUND(SUM(terminated_teu), 0) AS BIGINT) AS booking_terminated
  FROM source_data
),
monthly_totals AS (
  SELECT
    CAST(ROUND(SUM(booked_teu), 0) AS BIGINT) AS booked,
    CAST(ROUND(SUM(cancelled_teu), 0) AS BIGINT) AS cancelled,
    CAST(ROUND(SUM(rejected_teu), 0) AS BIGINT) AS rejected,
    CAST(ROUND(SUM(confirmed_teu), 0) AS BIGINT) AS confirmed
  FROM monthly_grain
),
booking_totals AS (
  SELECT
    CAST(ROUND(SUM(booked_teu), 0) AS BIGINT) AS booked,
    CAST(ROUND(SUM(confirmed_teu), 0) AS BIGINT) AS confirmed,
    CAST(ROUND(SUM(cancelled_teu), 0) AS BIGINT) AS cancelled,
    CAST(ROUND(SUM(rejected_teu), 0) AS BIGINT) AS rejected,
    CAST(ROUND(SUM(no_show_teu), 0) AS BIGINT) AS no_show,
    CAST(ROUND(SUM(terminated_teu), 0) AS BIGINT) AS terminated
  FROM booking_grain
),
comparison AS (
  SELECT 1 AS sort_order, 'Monthly' AS area, 'Booked TEU' AS metric,
         r.monthly_booked AS raw_wide_sum, m.booked AS correct_grain_total
  FROM raw_totals r CROSS JOIN monthly_totals m

  UNION ALL
  SELECT 2, 'Monthly', 'Cancelled TEU', r.monthly_cancelled, m.cancelled
  FROM raw_totals r CROSS JOIN monthly_totals m

  UNION ALL
  SELECT 3, 'Monthly', 'Rejected TEU', r.monthly_rejected, m.rejected
  FROM raw_totals r CROSS JOIN monthly_totals m

  UNION ALL
  SELECT 4, 'Monthly', 'Confirmed TEU', r.monthly_confirmed, m.confirmed
  FROM raw_totals r CROSS JOIN monthly_totals m

  UNION ALL
  SELECT 5, 'Booking', 'Booked TEU', r.booking_booked, b.booked
  FROM raw_totals r CROSS JOIN booking_totals b

  UNION ALL
  SELECT 6, 'Booking', 'Confirmed TEU', r.booking_confirmed, b.confirmed
  FROM raw_totals r CROSS JOIN booking_totals b

  UNION ALL
  SELECT 7, 'Booking', 'Cancelled TEU', r.booking_cancelled, b.cancelled
  FROM raw_totals r CROSS JOIN booking_totals b

  UNION ALL
  SELECT 8, 'Booking', 'Rejected TEU', r.booking_rejected, b.rejected
  FROM raw_totals r CROSS JOIN booking_totals b

  UNION ALL
  SELECT 9, 'Booking', 'No-show TEU', r.booking_no_show, b.no_show
  FROM raw_totals r CROSS JOIN booking_totals b

  UNION ALL
  SELECT 10, 'Booking', 'Terminated TEU', r.booking_terminated, b.terminated
  FROM raw_totals r CROSS JOIN booking_totals b
)
SELECT
  area,
  metric,
  raw_wide_sum,
  correct_grain_total,
  raw_wide_sum - correct_grain_total AS difference
FROM comparison
ORDER BY sort_order;
```

### Validate the output before taking the screenshot

The query must return exactly these ten rows:

| Area | Metric | Raw wide sum | Correct-grain total | Difference |
|---|---|---:|---:|---:|
| Monthly | Booked TEU | 1,549,331 | 256,071 | 1,293,260 |
| Monthly | Cancelled TEU | 378,095 | 63,262 | 314,833 |
| Monthly | Rejected TEU | 265,931 | 47,660 | 218,271 |
| Monthly | Confirmed TEU | 848,446 | 135,399 | 713,047 |
| Booking | Booked TEU | 256,714 | 248,607 | 8,107 |
| Booking | Confirmed TEU | 135,802 | 131,114 | 4,688 |
| Booking | Cancelled TEU | 63,433 | 61,325 | 2,108 |
| Booking | Rejected TEU | 47,711 | 46,640 | 1,071 |
| Booking | No-show TEU | 8,804 | 8,608 | 196 |
| Booking | Terminated TEU | 818 | 780 | 38 |

If any value differs, do not edit the SQL output or force it to match this table. First confirm that the query used version 86, August 2026 and the exact source table. If those are correct, treat the changed result as source drift and create a new evidence version instead of mixing values.

### Capture the output

1. Expand the result panel until all ten rows and all five columns are visible.
2. Keep the Databricks result-grid styling visible.
3. Hide or crop out the SQL editor; the report should show output, not code.
4. Exclude browser notifications, credentials, unrelated tabs and customer-level records.
5. Use Windows Snipping Tool to capture the result grid.
6. Save the image as `sql-ten-grain-comparisons-v86.png` in `Desktop\temp analysis`.

Use this caption in Word:

> Live Databricks output comparing direct wide-table sums with totals calculated once at each metric's validated business grain.

## Step 3: Confirm the production-main-agent evidence

Use only the existing production main agent. Do not use an Arm B agent, Arm C agent or personal Genie space in this report section.

For any screenshot that must be recaptured:

1. Start a fresh production-agent chat.
2. Ask one exact question from the evidence list above.
3. Wait for the complete answer.
4. Confirm the answer uses August 2026 and the requested metric.
5. Capture the full question, complete answer, returned total and enough interface chrome to identify the production main agent.
6. Do not expose unrelated conversations, credentials or customer-level detail.
7. Save the image using the exact evidence filename.

Do not ask multiple evidence questions in one chat. A fresh chat reduces carry-over from earlier prompts.

## Step 4: Apply the evidence-admission rule

A case belongs in this report only when every condition below is satisfied:

1. The question was asked in a fresh chat with the existing production main agent.
2. The agent question and SQL use August 2026 and the same metric.
3. The agent answer differs from the correct-grain total.
4. The agent answer exactly matches the live direct wide-table sum, allowing only displayed number formatting.
5. The live SQL demonstrates that the measure repeats across rows below its validated business grain.
6. The source version and timestamp are recorded.
7. Both the production-agent screenshot and live Databricks output are available.

Exclude a case when any of these conditions applies:

- The production agent gives the correct answer.
- The agent refuses the request or says it is unsupported.
- The agent selects a different metric.
- The question or answer uses another month or filter.
- The difference is only rounding.
- The cause cannot be tied specifically to repeated rows.
- The SQL evidence is from a different source version.

These ten cases are selected demonstrations of a known grain risk. Do not present them as the overall production-agent failure rate.

## Step 5: Replace the manual table in the existing Word report

1. Open `Desktop\temp analysis\csm csal v3 grain analysis report.docx`.
2. Find the heading `4. How the production-agent evidence was admitted`.
3. Keep the two explanatory paragraphs below the heading unchanged.
4. Select the complete manually formatted five-column table below those paragraphs.
5. Delete only that table.
6. Place the cursor at the same location.
7. In Word, choose **Insert**, **Pictures**, **This Device**.
8. Select `Desktop\temp analysis\sql-ten-grain-comparisons-v86.png`.
9. Set the image to **In Line with Text** so it moves safely with the document.
10. Resize it proportionally to the usable page width. Do not stretch it vertically.
11. Add the caption supplied in Step 2 directly under the image.
12. Keep the monthly and booking detail sections that follow. Do not remove the ten agent screenshots or the three existing SQL outputs used in those sections.
13. Save the same Word file. Do not use Save As to create another report.

### Fallback when one combined output cannot be captured

At the same table location, insert these genuine Databricks outputs in this order:

1. `sql-monthly-totals-v86.jpeg`
2. `sql-monthly-confirmed-v86-crop.png`
3. `sql-booking-totals-v86.jpeg`

Use these captions:

- Live SQL output for monthly booked, cancelled and rejected TEU.
- Live SQL output for monthly confirmed TEU.
- Live SQL output for the six booking-grain measures.

Do not use both the combined screenshot and the three fallback screenshots in section 4. Choose one approach to avoid duplication.

## Step 6: Keep the document in this order

The finished report should follow this story:

1. Title and purpose
2. Executive summary
3. Source period and version
4. Explanation of grain in this dataset
5. August structural-grain evidence
6. Proposed-model validation evidence
7. Production-evidence admission method
8. Genuine Databricks comparison output
9. Monthly evidence 1 through 4
10. Booking evidence 5 through 10
11. What the evidence proves
12. Limitations
13. V3 plan of action
14. Databricks notebook reference

## Step 7: Use factual explanations for the ten cases

The production answer, correct result and difference for each admitted case are:

| Evidence | Finding to explain |
|---|---|
| 1 | The production agent returned 1,549,331 monthly booked TEU, matching the direct wide sum. Counting the value once at monthly grain gives 256,071, a difference of 1,293,260. |
| 2 | The production agent returned 378,095 monthly cancelled TEU, matching the direct wide sum. The monthly-grain result is 63,262, a difference of 314,833. |
| 3 | The production agent returned 265,931 monthly rejected TEU, matching the direct wide sum. The monthly-grain result is 47,660, a difference of 218,271. |
| 4 | The production agent returned 848,446 monthly confirmed TEU, matching the direct wide sum. The monthly-grain result is 135,399, a difference of 713,047. |
| 5 | The production agent returned 256,714 booked TEU, matching the direct wide sum. The booking-grain result is 248,607, a difference of 8,107. |
| 6 | The production agent returned 135,802 confirmed TEU, matching the direct wide sum. The booking-grain result is 131,114, a difference of 4,688. |
| 7 | The production agent returned 63,433 cancelled TEU, matching the direct wide sum. The booking-grain result is 61,325, a difference of 2,108. |
| 8 | The production agent returned 47,711 rejected TEU, matching the direct wide sum. The booking-grain result is 46,640, a difference of 1,071. |
| 9 | The production agent returned 8,804 no-show TEU, matching the direct wide sum. The booking-grain result is 8,608, a difference of 196. |
| 10 | The production agent returned 818 terminated TEU, matching the direct wide sum. The booking-grain result is 780, a difference of 38. |

For monthly measures, the validated grain is:

`month + customer + sales_rep + agreement + service`

For booking measures, the validated grain is:

`customer + agreement + week_num + service + tcr`

Keep each explanation short and evidence-based. Do not describe missing columns as data loss because the report tests aggregation grain, not physical removal of source columns.

## Step 8: Final Word quality review

Complete every check before calling the report finished:

- Save and reopen the existing Word file from `Desktop\temp analysis`.
- Review the title page and every page containing a screenshot.
- Confirm that the Databricks comparison output is readable at normal zoom.
- Confirm that no screenshot is stretched, clipped, blurry or placed over text.
- Confirm that every caption is attached to the correct screenshot.
- Confirm that evidence numbers run from 1 to 10 without a gap or duplicate.
- Search for `Evidence image unavailable` and confirm that there are no matches.
- Confirm that the notebook reference points to notebook ID `1001878441092879`.
- Confirm that footers and page numbers are visible.
- Confirm that the replacement did not introduce an empty page.
- Search the live-evidence sections for outdated version-80 totals.
- Confirm that the live evidence consistently says version 86.
- Confirm that structural analysis consistently says version 80.
- Search for statements claiming that the 79-column production source was replaced, normalized in production or modified.
- Confirm that the report says production remained read-only.
- Confirm that the report does not claim the ten selected cases are a full production accuracy score.
- Save the document again after the review.

## Writing rules for the report

- Use clear, professional corporate English.
- Explain the evidence without blaming a team or individual.
- Use only statements supported by the captured outputs.
- Do not show SQL or notebook code in the Word report.
- Do not claim that source information was lost.
- Do not claim that the whole production agent is inaccurate.
- Do not claim that Arm B or Arm C is production-ready.
- Do not invent business keys, approved formulas or relationships.
- Do not expose credentials, tokens, customer-level rows or unrelated chats.
- State that all production investigation was read-only.

## Troubleshooting

### Version 86 is no longer available

Stop the version-86 recapture. Do not substitute a newer version while keeping the old answers. Record the new Delta version and timestamp, rerun the comparison query and re-ask all ten production questions in fresh chats. Save the new evidence with filenames containing the new version.

### A query value does not match the expected version-86 value

Confirm the source, month and version. If they are correct, do not overwrite or manually edit the output. Treat the difference as source drift or a reproducibility issue and investigate before using it.

### The result grid does not fit on screen

Collapse the SQL editor or drag the result panel upward, reduce browser zoom slightly, and fit all five columns before capturing. Do not make the result so small that it is unreadable in Word.

### The screenshot is unreadable in Word

Recapture a tighter result-grid crop at a larger scale. Keep the original aspect ratio and use **In Line with Text** in Word.

### The production answer does not match the raw wide sum

Do not include it as a grain-only failure. It may involve another metric, filter, business rule or agent behavior. Keep it outside this report unless a separate analysis proves the cause.

### The Word layout changes after insertion

Use **In Line with Text**, keep the image within page margins, insert a page break before the next major heading if necessary, and recheck the surrounding pages after saving.

## Remaining V3 work after the report

This report completes the focused production grain evidence. It does not complete the full three-arm comparison.

### Arm A: Production reference

Keep the existing production tables, production agent, instructions and UC functions unchanged. Use Arm A only as the production comparison reference.

### Arm B: Facts, dimensions and business views

Use all six documented Sales AI Gold sources:

- `csm_csal_summary`
- `fincon_issues`
- `sales_ai_roster`
- `sales_ai_case_ledger`
- `sales_ai_case_issues`
- `tea_deliverables`

Then:

1. Confirm the grain of each source.
2. Reuse compatible V2 work without changing V2.
3. Build personal dimensions and facts at validated business grains.
4. Preserve every source column.
5. Build focused business views for Genie.
6. Validate record preservation, totals, key quality, relationships and join duplication.

### Arm C: Normalized CSM/CSAL tables

Use `csm_csal_summary` as the source, then:

1. Build the personal normalized tables.
2. Give every table a defined primary key.
3. Prove that every primary key is unique and non-null.
4. Use corresponding foreign keys for every relationship.
5. Prove that populated foreign keys resolve to parent records.
6. Preserve and reconcile all 79 source columns.
7. Connect the normalized tables directly to Genie.

### Fair agent comparison

After Arm B and Arm C pass data validation:

1. Give the personal agents equivalent business instructions.
2. Give them equivalent examples and approved UC-function support where applicable.
3. Use preparation questions for tuning, then freeze both configurations.
4. Ask the same applicable questions across Arms A, B and C.
5. Use the same dates and verified expected answers.
6. Run every scored question three times in a fresh conversation.
7. Retain the answers, generated SQL when visible, errors and response times.
8. Compare accuracy, consistency, grain correctness, SQL complexity and response time.
9. Record source timestamps and configuration differences.
10. Report the outcome as a comparison of complete implementations, not as proof that data structure alone caused every difference.

No production tables, agent configuration, instructions or UC functions should be changed during this work.

## Final handoff statement

When every step above is complete, the report can be handed over with this wording:

> The document now contains the August 2026 structural grain analysis and ten paired live production-agent examples. Each admitted example is supported by a genuine Databricks output from the same Delta version and shows the difference between a direct wide-table sum and a total calculated once at the validated business grain. Production remained read-only. The evidence supports proceeding with a controlled Arm B and Arm C comparison; it does not claim that the current production agent is generally inaccurate or that either proposed design is already production-ready.
