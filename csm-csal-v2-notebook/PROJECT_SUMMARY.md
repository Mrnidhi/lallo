# CSM / CSAL V2: goal and current position

Updated: 10 September 2026

## Why we started

Simple CSM questions sometimes produce long SQL, use the wrong measure or return inconsistent results. The current 78-column Gold table is not automatically a bad design, but its similar fields and repeated grains can make the agent's job harder.

Our goal is to test whether a smaller, clearly defined booking view improves answer accuracy and consistency without changing production.

## What is already built

Inside the personal `usr.jayarsr` schema, the POC contains separate booking, commitment and allocation facts, supporting dimensions and a curated booking-scope view. Saved checks confirmed:

- the objects are Delta;
- keys do not collide;
- joins to dimensions do not multiply rows;
- booking and commitment totals stay stable;
- the booking view has one row per customer, agreement, week, service and TCR;
- the view row count matches the booking fact.

Two personal agents are ready:

- **Agent A, Wide Baseline:** uses the personal frozen copy of the 78-column Gold-shaped table.
- **Agent B, Booking Scope:** uses the personal curated booking view over the fact and dimension POC.

Production objects were not changed.

## What the formal test now covers

The controlled V2 experiment uses C01 to C07 only. These questions test:

1. lowest confirmed utilization;
2. stored low-booking signals;
3. stored high-cancellation signals;
4. stored high-rejection signals;
5. stored above-CSAL signals;
6. one booking summary without repeated-grain inflation;
7. an exact customer no-match guardrail.

Each question is asked through both agents three times. This gives 42 formal trials, 21 per agent.

Expected answers were calculated independently through three paths: versioned wide-table SQL, a separate DataFrame calculation and the curated view. The results are engineering-cross-checked, but they are not a business owner's policy sign-off.

## Why the older 12-question run was narrowed

The Daily Outlook source refreshed while the earlier mixed-domain test was running. Its table version changed, while every CSM source, schema and booking-view definition stayed the same.

Mixing that unrelated refresh into the architecture score would make the comparison unfair. Finance, cases, Daily Outlook and cross-domain routing therefore remain separate smoke tests. They can be tested later without changing the CSM result.

## Where we stand

- Foundation and agents: complete.
- Structural validation: complete and passing.
- CSM question wording and reference answers: complete for C01 to C07.
- Safe runner, review helper, report and chart: ready and locally tested.
- New formal CSM submissions: 0 of 42.
- Overall project progress: approximately 70%.

The earlier `routing_01` C01 pair remains separate pilot evidence. Both personal agents returned the correct 20 rows in that pilot. It is not copied into the new experiment.

Two production-main-agent observations are also separate:

- C01 returned no business rows after its own internal attempts.
- C02 understood the question but returned a summary instead of the requested 20-row result.

They are useful examples of the current experience, not formal A/B scores.

## What remains

1. Restore the Windows VM session.
2. Start the separate CSM-only checkpoint.
3. Run all 21 matched A/B pairs without automatic retries.
4. Review each saved answer against its expected rows.
5. Report task success, repeat consistency, failures, grain handling and client response time.
6. Report SQL complexity only where the original SQL trace is available.
7. Produce the final chart and manager summary.

## What the final conclusion can say

This experiment can show whether the personal curated booking access path performs better than the personal wide-table path for these seven CSM questions.

It cannot prove that facts and dimensions alone caused the result. The curated path also has fewer columns, clearer names, a fixed grain, stored metrics, reader instructions and routing. It also cannot justify a full production redesign by itself.

Historical threshold calibration, actual-event enrichment and swap scoring remain parked for the later phase.
