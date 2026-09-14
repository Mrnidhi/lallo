# CSM/CSAL Grain Fix Scope Assessment

## Short conclusion

The screenshots do not show that every grain in `csm_csal_summary` was corrected.

They show that the team addressed one specific duplication path: swap demand in the Daily Outlook, where the same customer, contract, SWD and TCR could appear on more than one row because of different sail weeks. The message says the Daily Outlook should stop double-counting swap demand after the job is rerun.

That is a targeted correction. It is not evidence that the complete 79-column table now has one universal grain or that every business metric can be summed safely.

## What the first screenshot shows

The Databricks query creates two correct-grain projections:

- Monthly grain: `month + customer + sales_rep + agreement + service`
- Booking grain: `customer + agreement + week_num + service + tcr`

The result then compares a direct sum from the physical wide rows with a total calculated once at the appropriate business grain.

Every displayed metric still has a non-zero difference between `raw_wide_sum` and `correct_grain_total`. This means the current wide rows still repeat monthly and booking values. The SQL query corrects the totals while reading the data; it does not prove that the underlying source table was normalized or that its grains were redesigned.

The screenshot also appears to query the current table without `VERSION AS OF`. Therefore, its values should not be mixed with the earlier version-86 report values until the current Delta version and timestamp are recorded.

## What the second screenshot shows

The relevant team update says that a duplicate-record problem affecting swap demand in the Daily Outlook was fixed and would take effect after the job reran.

Another visible update about missing watch hits, skill filtering and fallback logic is a separate agent-behaviour issue. It is not evidence of a CSM/CSAL grain correction.

## Current status by business area

| Business area | Current evidence-based status |
|---|---|
| Daily Outlook swap demand | A targeted double-counting fix was reported. Confirm the post-rerun output before marking it verified. |
| Monthly booked, confirmed, cancelled and rejected TEU | The current Databricks comparison still shows raw totals different from monthly-grain totals. Direct wide-row summation remains unsafe. |
| Booking booked, confirmed, cancelled, rejected, no-show and terminated TEU | The current comparison still shows raw totals different from booking-grain totals. Direct wide-row summation remains unsafe. |
| Allocation measures | Earlier August version-80 analysis found no repetition for selected allocation-level additive measures when used at the full allocation grain. This has not been revalidated for every current column after the latest refresh. |
| Commitment | Earlier analysis showed `total_reviewed_teu` belongs to customer, agreement, week and service grain and can repeat across lower-level TCR or category rows. |
| MQC and agreement context | Earlier analysis showed `sc_mqc`, `ctd_vol` and `ctd_prorated_mqc` belong to agreement context and repeat across detailed rows. |
| Rates, percentages and averages | These cannot be declared correct from row deduplication alone. They require the approved numerator, denominator and weighting rule. They must not be summed or averaged blindly. |
| Flags, status text, cutoff fields and issue fields | These are generally used for filtering or display rather than addition. Their correct scope still matters, and some were observed to vary by allocation category or sales representative. |
| CRM case context | The one-month sample showed stable values at the tested agreement context, but this does not prove all periods or current versions. |
| All 79 columns | Column preservation and proposed grain mapping passed in the August design analysis. A complete post-fix business validation of every column has not yet been performed. |

## Why only swap demand was mentioned as fixed

The reported production defect was specifically about duplicate swap-demand records in the Daily Outlook. Engineering fixes are normally scoped to the failing transformation or consuming feature that was reported. Unless the team also changed the shared source grain and revalidated all dependent measures, a fix in that path does not automatically correct monthly performance, booking, commitment, MQC or CRM calculations.

## What must be checked before saying the grains are fixed

1. Record the current Delta version and timestamp after the production job rerun.
2. Verify that the specific duplicate swap-demand key no longer produces multiple records in the Daily Outlook output.
3. Rerun the full raw-versus-correct-grain reconciliation against that same version.
4. Check every additive measure at its mapped grain, not only the ten demonstration metrics.
5. Separately validate ratios, averages, flags and descriptive fields using their approved business rules.
6. Ask the same questions through the production main agent and compare each answer with SQL from the same Delta version.
7. Record which items pass, fail or remain unverified. Do not convert an untested metric into a pass.

## Safe statement for a review meeting

> The team corrected a specific duplicate-record issue affecting swap demand in the Daily Outlook. That is useful, but it is not yet a complete grain redesign of the CSM/CSAL source. Our latest comparison still shows that several monthly and booking measures differ when summed directly from the wide rows versus counted once at their business grain. We should rebaseline the current Delta version and validate every metric group before saying the grain problem is fully resolved.

## Decision

Do not remove the V3 grain work. Treat the production swap-demand change as one targeted fix and add it as a post-fix test case. Continue the planned metric-to-grain validation and three-arm comparison.
