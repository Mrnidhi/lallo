# CSM / CSAL V2: goal and current position

Updated: 10 September 2026

## Goal

Test whether a smaller, clearly grained CSM booking interface helps sales agents answer more accurately and consistently than a frozen copy of the 78-column Gold-shaped table, without changing production.

## What was built

In `usr.jayarsr`, the personal POC contains seven dimensions, three facts and one 29-column booking view. The booking view exposes booking measures at customer + agreement + week + service + TCR, while reviewed commitment keeps its customer + agreement + week + service meaning.

Two personal main agents formed the comparison:

- A used the frozen 78-column wide source through `CSM Wide Baseline V2`.
- B used `agent_booking_risk_current_poc_v2_v23` through `CSM Booking Scope V2`.

Their other four specialist readers were the same. Production was not a formal benchmark arm and was not changed.

## Validation completed

- All saved fact, dimension and view relationship checks passed.
- Row counts and checked TEU measures remained stable through joins.
- C01-C07 reference calculations were technically cross-checked for the frozen snapshot.
- All 42 planned personal A/B responses completed and were saved once.
- The deterministic scorer, readable summary, failure review and SQL-evidence audit completed.
- The canonical notebook cells pass 44 local regression tests.

## Result

| Measure | Wide A | Curated B |
|---|---:|---:|
| Proven correct out of 21 planned runs | 12 | 13 |
| Accuracy across 18 C01-C06 table-answer runs | 66.7% | 72.2% |
| Stable comparable question groups | 3 of 4 | 3 of 4 |
| Median client response time | 40.98 s | 40.09 s |
| Clear C07 no-match statements | 3 of 3 | 3 of 3 |

The curated path was one answer better. No clear consistency or latency winner was observed. C07 narratives were correct, but exact-filter retrieval could not be proven without executed SQL. Structured SQL correctness, source routing, SQL duration and query complexity remain not evaluated.

## Decision

Keep production unchanged. Retain the curated view as a personal pilot, improve the output contract for C01, C03 and C06, capture structured SQL/tool traces and rerun the same 42-trial design under a new version.

This result does not justify replacing the full Gold layer or prove that facts and dimensions alone caused the small accuracy difference. The Databricks-managed model and actual per-request warehouse use were not independently verified.

## Later work

The remaining 41-question coverage, hard sales-rep scenarios, historical threshold calibration, actual-event enrichment and swap scoring are separate follow-up phases. Their expected answers must be verified before they are used as benchmark ground truth.

- [Notebook guide](README.md)
- [Question bank](question_bank.md)
- [Full controlled result](reports/csm-csal-v2-controlled-benchmark-results-2026-09-10.md)
