# CSM CSAL V3 Ten Evidence Questions

These are the ten varied cases discussed in the [ten-case report](csm-csal-v3-final-grain-evidence-report.md). They cover a filtered total, a commitment total, a subtraction, an average, a percentage, a ranking, detail and parent values, structural counts, unique cases and an allocation control.

This is the current question list for taking new screenshots. The older monthly and booking metric list uses the same E-numbers for different questions. Do not mix the two lists.

## Before you start

1. Open the existing production main agent inside the Windows VM.
2. Start a fresh conversation for each case. Copy only the question from its block below.
3. For E01 and E07, fill the customer and agreement fields from the matching saved SQL or result inside the VM. Keep the same values in the agent question and the validation SQL.
4. Keep August 2026 as the reporting month for this set. If you change the period, change both the questions and the SQL and record this as a new run.
5. Save the complete first response, including a clarification request, error or unavailable answer. Keep any follow-up in the same case record. Do not keep retrying until an answer differs.

These prompts restate the recorded case descriptions for a new run. E06 explicitly states the ranking level used by the saved SQL. They are not a verbatim transcript of every earlier question, and a new answer may differ from the historical result.

## E01 Filtered booked TEU

Copy the customer and agreement from the saved Test 01 filters. The recorded case uses week `2026WK31`, service `PVCS` and TCR `HKG`. Replace both bracketed fields before sending.

```text
For August 2026, what is the booked TEU for customer [CUSTOMER], agreement [AGREEMENT], reporting week 2026WK31, service PVCS and TCR HKG?
```

Capture the full question and answer. In the SQL capture, show the same customer, agreement, week, service and TCR. If those filters return no current data, retain that outcome rather than silently choosing another case.

## E02 Portfolio reviewed commitment

```text
What is the total reviewed commitment TEU for August 2026?
```

Keep this separate from E10, which asks about reviewed allocation. The reference calculation must use the commitment definition.

## E03 Booked volume after cancellations

```text
For August 2026, what is the booked TEU after cancelled TEU is removed? Please show the booked TEU, cancelled TEU and the resulting net TEU.
```

Capture all three amounts. The saved analysis compares native booking and monthly producer calculations. Record which metric definitions the agent uses before deciding whether the answers are comparable.

## E04 Average SC MQC per distinct agreement

```text
Across the distinct agreements represented in the August 2026 CSM/CSAL data, what is the average SC MQC? Please include the number of agreements used and explain how missing SC MQC values are handled.
```

Capture the average, agreement count and any missing-value explanation. Compare the same agreement population and definition in SQL.

## E05 Portfolio cancellation percentage

```text
What percentage of August 2026 booked TEU was cancelled? Please show the cancelled TEU, booked TEU and cancellation percentage used in your answer.
```

Capture the numerator, denominator and percentage. A percentage can differ because of the values used or their weighting, so retain all three.

## E06 Top five no-show booking combinations

```text
For August 2026, which five combinations of customer, agreement, reporting week, service and TCR have the highest no-show TEU? Show all five identifying fields and the no-show TEU for each result. Mention any tie at fifth place.
```

Capture all five rows and any tie explanation. The saved SQL ranks these five-field combinations. It does not rank totals grouped only by customer and agreement. This wording makes that distinction explicit for the new run.

## E07 TCR detail and parent commitment

Fill the customer and agreement from the saved Test 07 output for week `2026WK32` and service `ECX1`. Confirm that the detail contains TCR `ECN`.

```text
For August 2026, customer [CUSTOMER], agreement [AGREEMENT], reporting week 2026WK32 and service ECX1, what is the confirmed TEU for TCR ECN? Also show the reviewed commitment TEU for the same customer, agreement, week and service across all TCRs.
```

Capture both answers. Compare the ECN detail and the parent commitment separately. The saved Test 07 code selects an example dynamically, so a later run can select a different customer or scope. If that happens, use all the new selected filters consistently and label it as a new example.

## E08 Categories and volume without CSAL flags

```text
For August 2026, group the CSM/CSAL data by customer, agreement, reporting week, service and TCR. How many combinations are there in total, how many appear in more than one category, and how many contain different values of the volume-without-CSAL flag? Please explain how missing category or flag values are handled.
```

Capture all three counts and the missing-value explanation. The saved SQL ignores null categories when counting distinct categories, but treats a null flag as a distinct flag value. If the agent uses a different rule, record the difference before comparing the totals.

## E09 Unique active IB CSAL cases

```text
For the agreements represented in the August 2026 CSM/CSAL data, how many distinct active IB CSAL monitoring cases are present? Count each case once and explain which case statuses and dates you include. Report the answer only. Do not create cases, tasks or alerts.
```

Capture the count and its scope. The saved source check uses contract-linked monitoring cases, excludes status code 6, limits creation dates to 1 July 2026 onward, and selects the latest modified case per agreement before counting distinct case IDs. Those are the saved producer rules, not proof of the intended business definition. Compare only after checking whether the agent and SQL apply the same rule. Keep any latest-date ties or unresolved matches visible.

## E10 Reviewed allocation TEU

```text
What is the total reviewed allocation TEU for August 2026?
```

Capture the answer and any definition provided. This is the allocation control case, separate from the reviewed commitment in E02.

## Save the screenshots

Create a folder inside the Windows VM:

`Desktop\temp analysis\ten evidence questions\[RUN-DATE-TIME]`

For every case, use these labels:

- `E01-A-agent.png` for the question and complete production-agent answer.
- `E01-B-sql-code.png` for the actual validation SQL with its filters and calculation visible.
- `E01-C-sql-result.png` for the result of that SQL, including unresolved counts and status.

Replace E01 with the relevant ID. Use `A1` and `A2`, or `B1` and `B2`, if the content needs more than one readable image. For E06, make sure all five rows are visible. For E07, retain both detail and parent results.

Use Windows Snipping Tool inside the VM. Close menus that cover the evidence and save the image in the case folder. Keep the question, numbers and column headings readable. Do not use recreated tables as SQL screenshots.

If the production interface exposes the actual SQL, UC function or tool trace, save it as `E01-D-agent-trace.png`. Screenshot B is the manual validation query, which may differ from the agent's own query.

Record the conversation reference, query or notebook link, run time, filters and data version where available. If the agent version or source version is unavailable, record that rather than assuming it matches. Do not pair a new agent response with an old SQL result as if they were the same run.

Keep historical totals out of the prompts. Preserve correct answers and unresolved cases as well as mismatches. The question set does not require ten failures.

## Attach to the report

Use A for the production answer, B after the SQL explanation, and C after B. Add the screenshot reference below each image. Retain D when available to support an explanation of the agent's calculation.

The [seven-case screenshot guide](csm-csal-v3-seven-evidence-screenshot-guide.md) covers E01, E02, E05, E07, E08, E09 and E10. E03, E04 and E06 belong to the full ten-case set. Older files named E09 or E10 may refer to different metrics, so match the subject and filters rather than the filename alone.

The [manager update Word document](CSM-CSAL-Grain-Analysis-Manager-Update.docx) uses four screenshot placeholders for the E01 example. Those placeholders are not ten separate evidence cases.
