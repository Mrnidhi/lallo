# CSM / CSAL V2: wide table versus curated booking view

Status: controlled personal proof of concept complete
Formal scope: C01 to C07, 42 total runs

## The problem

The frozen production-shaped baseline contains 78 columns, similar measures and repeated values at more than one useful business grain. That can make an agent's query task ambiguous even for a simple sales question.

## What we built

Production was not changed. In the personal workspace we kept the wide-table path as the baseline and added a smaller booking-scope view over the validated fact and dimension POC.

```text
Current Gold-shaped table                         Curated V2 path
78-column personal frozen copy                    booking fact + commitment fact + dimensions
              |                                                  |
CSM Wide Baseline V2 agent                        29-column booking-scope view
                                                                 |
                                                  CSM Booking Scope V2 agent
```

Both agents received the same question wording and were configured with the same intended warehouse and matched routing contract. Actual per-request warehouse use and equality of the Databricks-managed underlying model were not independently verified, so this compares the complete setups rather than isolating the data model alone.

## How we test it

- Seven CSM questions, technically cross-checked for the frozen snapshot, cover utilization, low booking, cancellation, rejection, above-CSAL demand, repeated-grain handling and an exact no-match case.
- Each question is asked three times through both personal agents.
- Expected rows come from independently cross-checked calculations, not from an agent answer.
- Calls are interleaved, saved once and never silently retried.
- Production-agent checks are kept as a separate smoke appendix because production has different orchestration and hidden runtime details.

## Final result

| Measure | Wide baseline | Curated booking view |
|---|---:|---:|
| Proven correct answers out of 21 planned runs | 12 (57.1%) | 13 (61.9%) |
| Accuracy across the 18 C01-C06 table-answer runs | 66.7% | 72.2% |
| Stable comparable question groups | 3 of 4 | 3 of 4 |
| Completed responses out of 21 | 21 | 21 |
| Median client response time | 40.98 seconds | 40.09 seconds |
| Clear C07 no-match statements | 3 of 3 | 3 of 3 |
| Assigned-source SQL trace captured | 0 of 21 | 0 of 21 |

The curated view produced one additional correct response, a 5.5 percentage-point improvement across the C01-C06 table-answer runs. This is directionally useful but not a decisive architecture win. Both paths were stable for three of the four question groups with comparable answer signatures. No clear latency winner was observed.

The remaining misses were concentrated in three areas: one unstable C01 ranking on each path, a required agreement field that could not be recognized for some C03 responses, and a missing recognized confirmed-TEU field for every C06 response. Both paths handled the C07 no-match wording correctly, but the exact query was not visible.

## How to interpret the result

The primary score is correct answers out of all 21 planned runs per agent. This keeps unproven no-match retrieval visible instead of converting it into an automatic pass.

Any improvement should be described as an improvement from the complete curated access path. That path combines fewer columns, clearer names, a defined row grain, stored measures, reader instructions and routing. This V2 test cannot prove that facts and dimensions alone caused the change.

The stored high-cancellation, high-rejection, low-booking and above-CSAL flags are tested exactly as they exist today. Their current thresholds are not validated by this benchmark. Historical threshold calibration remains a later, separate analysis.

## Recommendation

Keep the production Gold table unchanged. Retain the curated booking view as a personal pilot, tighten the agent response contract and add structured SQL trace capture. Then rerun the same seven questions as a new version before expanding to more domains.

Do not recommend a full production redesign from this seven-question POC alone. The test supports continuing the curated-view pattern, not migrating the complete Gold layer.

## Selected production observations

- C01: the production main agent returned no business rows after its internal attempts.
- C02: the production main agent understood the request but returned only a summary instead of the requested 20-row detail.

These are useful experience checks, not part of the formal A/B score. The separate smoke appendix contains mixed findings on both the production and personal sides and should not be combined with the controlled result.

## Next phase after V2

The completed result is sufficient to decide that the booking-view pattern deserves one corrective round. It is not sufficient to validate the full 41-question bank. Actual-event enrichment, historical threshold calibration and swap-receiver scoring remain parked until their data requirements and ground truth are ready.

Full sanitized evidence is saved in [the controlled benchmark result](csm-csal-v2-controlled-benchmark-results-2026-09-10.md).

The presentation-ready chart is saved in [the standalone benchmark visual](csm-csal-v2-controlled-benchmark-visual-2026-09-10.html).

## Databricks design basis

This POC follows Databricks guidance to keep a Genie data model focused, expose only necessary columns, add clear semantic metadata and use curated views when they simplify the agent's work. Databricks also recommends realistic benchmark questions with verified SQL and repeated wording tests because Genie responses can vary.

A normal view is a semantic layer, not a performance cache. If the curated path improves correctness but remains slow, a materialized view or table-optimization study should be evaluated separately rather than assuming the fact/dimension model will reduce latency.

- [Curate an effective Genie Agent](https://docs.databricks.com/aws/en/genie-agents/best-practices)
- [Test and monitor a Genie Agent](https://docs.databricks.com/aws/en/genie-agents/monitor)
- [Databricks views](https://docs.databricks.com/aws/en/views)
- [Standalone materialized views](https://docs.databricks.com/aws/en/ldp/dbsql/materialized)
