# CSM CSAL V3 Seven Strong Evidence Cases

**August 2026 production main agent and grain validation**

## Purpose and scope

I reviewed seven production-agent cases with a captured agent answer and a documented SQL comparison. I selected these cases because the available evidence supports a clear outcome or a clear limitation. Strong evidence describes the quality of the comparison. It does not mean that every case is a confirmed grain failure.

A grain is the business level at which a value should be counted once. When a higher-level value is repeated across detailed Gold rows, adding every row can overstate the result. I tested whether that pattern explains each agent answer.

The evidence comes from captured runs. The values are assessed within each run and are not presented as one frozen data snapshot. In this report, a pass means that the agent agrees with the tested calculation. It does not replace final confirmation of the business definition by the data owner.

All production-agent, SQL-code and SQL-result screenshots must be captured and inserted inside the Windows VM. This Markdown keeps placeholders only. It does not contain corporate screenshots or row-level data.

Use the [seven-evidence screenshot guide](csm-csal-v3-seven-evidence-screenshot-guide.md) to capture, name, verify and insert every image. The guide also lists screenshots from older numbering schemes that must not be reused.

## Assessment method

For each case, I compared the production-agent answer with the relevant source or producer result. I then compared it with the value counted once at the tested business grain. Where row repetition was relevant, I also calculated the result across the repeated Gold rows.

I used five outcome labels:

- Confirmed grain failure means the source and count-once values agree, the agent matches the repeated Gold result, and no material check remains open.
- Pass means the agent agrees with the tested calculation.
- Mixed result means different parts of the same response produce different outcomes.
- Strong grain-risk indication means the agent follows the repeated result, but an unresolved check prevents final confirmation.
- Does not reconcile means the agent does not agree with the tested SQL, but the available evidence does not isolate grain as the cause.

## Results at a glance

- E01 is a confirmed grain failure. The agent returned 432 TEU instead of the source and count-once value of 144 TEU.
- E02 passes. The agent returned the tested commitment value of 48,389 TEU.
- E05 is a strong grain-risk indication. The agent percentage exactly matches the repeated Gold calculation, but one record remains unresolved.
- E07 is mixed. The TCR detail matches the repeated result, while the parent commitment passes.
- E08 does not reconcile. The cause is not isolated.
- E09 does not reconcile. The cause is not isolated.
- E10 passes and provides a useful control because every tested path returns 48,389 TEU.

## E01 Filtered booked TEU

**Business question**

For one selected customer and agreement in week 2026WK31, service PVCS and TCR HKG, what is the booked TEU?

**Production agent answer**

The agent returned 432 TEU.

**SQL validation**

The source calculation returns 144 TEU. Counting the value once at the tested booking grain also returns 144 TEU. Adding the repeated Gold rows returns 432 TEU. No record remains unresolved in this case.

**Interpretation**

The agent answer is three times the source value and exactly matches the repeated Gold result. Because the source and count-once calculations agree and the checks are complete, the repeated Gold rows explain the difference within this captured run.

**Outcome**

Confirmed grain failure within the captured run.

`[VM SCREENSHOT E01-A: Production main-agent question and answer]`

`[VM SCREENSHOT E01-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E01-C: Databricks SQL result]`

## E02 Portfolio reviewed commitment

**Business question**

What is the total reviewed commitment TEU for August 2026?

**Production agent answer**

The agent returned 48,389 TEU.

**SQL validation**

The source result is 48,389 TEU, and the count-once result is also 48,389 TEU. Adding the repeated Gold rows would produce 115,396 TEU. No record remains unresolved.

**Interpretation**

The agent answer agrees with the source and count-once results. It does not match the repeated Gold total. The captured answer is correct against the tested calculation.

**Outcome**

Pass.

`[VM SCREENSHOT E02-A: Production main-agent question and answer]`

`[VM SCREENSHOT E02-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E02-C: Databricks SQL result]`

## E05 Portfolio cancellation percentage

**Business question**

What percentage of August 2026 booked TEU was cancelled?

**Production agent answer**

The agent returned 18,202 cancelled TEU, 103,364 booked TEU and a cancellation percentage of 17.609613 percent.

**SQL validation**

The native booking calculation gives 17.033035 percent. The Gold count-once calculation gives 17.033388 percent. The calculation across repeated Gold rows gives 17.609613 percent. One record remains unresolved.

**Interpretation**

The agent percentage exactly matches the repeated Gold calculation. This strongly indicates repeated-row weighting. I am not classifying it as confirmed because one record still needs to be resolved.

**Outcome**

Strong grain-risk indication. Final confirmation remains open.

`[VM SCREENSHOT E05-A: Production main-agent question and answer]`

`[VM SCREENSHOT E05-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E05-C: Databricks SQL result]`

## E07 TCR detail and parent commitment

**Business question**

For one selected customer and agreement in week 2026WK32 and service ECX1, what is the confirmed ECN TEU and the parent reviewed commitment?

**Production agent answer**

The agent returned 112 confirmed TEU for ECN and 59 TEU for the parent reviewed commitment.

**SQL validation**

The source and count-once ECN result is 56 TEU. The repeated ECN result is 112 TEU. The parent source and count-once result is 59 TEU, while the repeated parent value is 708 TEU.

**Interpretation**

At TCR detail, the agent answer matches the repeated Gold result and is twice the source and count-once value. At parent level, the agent answer agrees with the source and count-once result. These are separate metrics and must be judged separately. The comparison shows the observed outcomes. It does not establish which SQL path the agent used.

**Outcome**

Mixed result. The TCR detail shows a grain-related mismatch within the captured comparison. The parent commitment passes.

`[VM SCREENSHOT E07-A: Production main-agent question and answer]`

`[VM SCREENSHOT E07-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E07-C: Databricks SQL result]`

## E08 Category and volume without CSAL structure

**Business question**

How many booking combinations span more than one category, and how many have conflicting volume-without-CSAL flags?

**Production agent answer**

The agent returned 1,235 multi-category combinations and 1,163 combinations with conflicting flags.

**SQL validation**

Across 12,403 booking combinations, the SQL found 283 combinations in multiple categories and 195 with conflicting flags.

**Interpretation**

Both agent counts differ materially from the tested SQL result. The differences do not follow a clear repeated-row multiplier. Grouping, filters or interpretation may be involved, so this case does not prove a grain failure.

**Outcome**

Does not reconcile. The cause is not isolated, and grain is not established as the cause.

`[VM SCREENSHOT E08-A: Production main-agent question and answer]`

`[VM SCREENSHOT E08-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E08-C: Databricks SQL result]`

## E09 Unique active IB CSAL cases

**Business question**

How many active IB CSAL monitoring cases are present when each case is counted once?

**Production agent answer**

The agent returned 390 cases.

**SQL validation**

The source and count-once result is 444 unique active cases. Counting repeated Gold rows gives 12,452. Three case comparisons remain unresolved.

**Interpretation**

The agent result matches neither the unique-case count nor the repeated Gold total. The available evidence cannot reconstruct how 390 was produced. The three unresolved comparisons also prevent a stronger conclusion about the cause.

**Outcome**

Does not reconcile and remains unresolved. This is not a confirmed grain failure.

`[VM SCREENSHOT E09-A: Production main-agent question and answer]`

`[VM SCREENSHOT E09-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E09-C: Databricks SQL result]`

## E10 Reviewed allocation TEU control

**Business question**

What is the total reviewed allocation TEU for August 2026?

**Production agent answer**

The agent returned 48,389 TEU.

**SQL validation**

The source, allocation-grain and Gold calculations all return 48,389 TEU. No record remains unresolved.

**Interpretation**

The agent answer agrees with every tested calculation. Because every path returns the same number, this case confirms the answer but does not identify which calculation path the agent used.

**Outcome**

Pass and control case.

`[VM SCREENSHOT E10-A: Production main-agent question and answer]`

`[VM SCREENSHOT E10-B: Databricks SQL code used for validation]`

`[VM SCREENSHOT E10-C: Databricks SQL result]`

## Overall conclusion

The seven cases support a focused conclusion. E01 contains a confirmed grain failure within the captured run. E07 is mixed, with a grain-related mismatch at TCR detail and a passing parent-level answer. E05 strongly follows repeated-row weighting, but one open comparison prevents final confirmation.

E02 and E10 are clear passes against their tested calculations and provide controls for future testing. E08 and E09 are genuine mismatches, but the current evidence does not prove that grain caused them.

The next step is to correct and retest E01 and the TCR-detail part of E07, close the remaining E05 record, and trace the grouping and filters behind E08 and E09. E02 and E10 should remain unchanged as regression controls. The same seven questions can then be used to compare the production agent with the V3 personal implementations.

## Notebook reference

[Open the detailed CSM CSAL grain validation notebook](https://adb-2358492928897930.10.azuredatabricks.net/editor/notebooks/1001878441092879?o=2358492928897930)

The notebook contains the column mapping, grain checks, key checks, round-trip reconstruction and numerical reconciliation used for this report.
