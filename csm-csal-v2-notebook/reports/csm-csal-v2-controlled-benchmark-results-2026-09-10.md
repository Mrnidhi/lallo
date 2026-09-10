# CSM / CSAL V2 controlled benchmark result

Date: 10 September 2026

Status: personal proof of concept complete
Production changes: none

## Decision

Keep the current production Gold table unchanged. Keep the curated booking view as a promising personal proof of concept, but do not approve a full fact-and-dimension migration from this result alone.

The curated path produced one more correct answer than the wide path. It did not show a clear speed or consistency advantage. The next improvement should be a tighter agent output contract and complete SQL trace capture, followed by a rerun of the same seven questions.

## What was compared

| Before path | After path |
|---|---|
| Personal frozen copy of the 78-column Gold-shaped CSM table | Personal 29-column booking view over the validated booking fact, commitment fact and five shared dimensions |
| `CSM Wide Baseline V2` specialist | `CSM Booking Scope V2` specialist |
| `sales-ai-wide-baseline-v2` main agent | `sales-ai-booking-scope-v2` main agent |

Both personal main agents used the same four other specialist readers. Production was not used as a formal third test arm.

## Test method

- Seven verified booking-scope questions, C01 to C07
- Two personal agents
- Three repetitions per question and agent
- 42 planned responses and 42 completed responses
- Same question wording and result rules; both arms were configured with the same intended warehouse and matched routing contract
- Independently calculated reference rows
- Interleaved A/B calls with no silent retry
- Source state remained unchanged for all 42 calls

The reference calculations were cross-checked technically for this frozen snapshot. Actual per-request warehouse use and equality of the Databricks-managed underlying model were not independently verified. The result therefore compares the complete configured setups. It is not a business owner's approval of the current risk thresholds.

## Main result

| Measure | Wide baseline | Curated booking view |
|---|---:|---:|
| Proven correct out of all 21 planned runs | 12/21 (57.1%) | 13/21 (61.9%) |
| Accuracy across the 18 C01-C06 table-answer runs | 12/18 (66.7%) | 13/18 (72.2%) |
| Stable comparable question groups | 3/4 | 3/4 |
| Median client response time | 40.98 seconds | 40.09 seconds |
| Clear C07 no-match statements | 3/3 | 3/3 |
| Recorded source state unchanged | 21/21 | 21/21 |

The curated view improved C01-C06 table-answer accuracy by 5.5 percentage points, which is one additional correct run. This is a useful signal, but it is not yet a strong architecture win. Both paths were stable for three of the four question groups with comparable answer signatures; C03 and C06 lacked required recognizable fields and C07 was assessed separately as a narrative guardrail.

No clear latency winner was observed. The overall client end-to-end median was 0.89 seconds lower for the curated path, while the median matched-pair difference was 0.76 seconds in the other direction. No equivalence threshold or statistical latency test was defined, so this small and mixed result does not support a speed claim.

## Question-level result

| Question | What it tests | Wide | Curated | What happened |
|---|---|---:|---:|---|
| C01 | Lowest confirmed utilization | 2/3 | 2/3 | Each path returned a different row set or value once. Both were unstable. |
| C02 | Stored low-booking flag | 3/3 | 3/3 | Both were correct and stable. |
| C03 | Stored high-cancellation flag | 1/3 | 2/3 | This was primarily an output-contract failure: a required agreement field was not recognized, so the calculation could not be fully verified. |
| C04 | Stored high-rejection flag | 3/3 | 3/3 | Both were correct and stable. |
| C05 | Stored above-CSAL flag | 3/3 | 3/3 | Both were correct and stable. |
| C06 | Exact five-key booking lookup | 0/3 | 0/3 | Both omitted a recognized confirmed-TEU field in all three responses. This is an output-contract failure. |
| C07 | Exact customer no-match | 3/3 narrative checks | 3/3 narrative checks | Both clearly reported no match and did not substitute another customer. Exact-filter SQL was not visible, so retrieval correctness remains unproven. |

## SQL evidence

The saved responses contained SQL-like text in 11 of 21 wide-path trials and 13 of 21 curated-path trials. None of those saved strings named the assigned CSM source. They cannot be treated as complete executed SQL traces.

For this reason, SQL correctness, source routing, SQL execution time and before-versus-after SQL complexity remain **not evaluated**. The report does not guess these values.

## What this proves

- Earlier structural checks passed for the tested booking grain; this agent benchmark then showed that the curated view was usable.
- The curated view can answer the main booking-risk patterns and had a small accuracy edge in this run.
- Data organization alone did not remove response-format and ranking variability.
- The current POC is safe to continue because it did not require a production change.

## What this does not prove

- It does not prove that the complete 78-column Gold table should be replaced.
- It does not prove that facts and dimensions alone caused the accuracy difference.
- It does not validate allocation, monthly, MQC, finance, case, sales-representative or multi-domain questions.
- It does not validate the current hard-coded cancellation, rejection or booking thresholds.
- It does not validate historical trends, actual-event enrichment or swap recommendations.

## Reproducibility markers

- Experiment: `sales_ai_v2_csm_controlled_01`
- Code version: `v2_csm_controlled_2026-09-10`
- Wide source: `usr.jayarsr.src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23`
- Original Gold snapshot recorded by the experiment: version 32
- Curated source: `usr.jayarsr.agent_booking_risk_current_poc_v2_v23`
- Reference status: `CALCULATIONS_CROSS_CHECKED_NOT_BUSINESS_SIGNED_OFF`
- The checkpoint manifest stores prompt, method, wording, source and view fingerprints. It remains inside the personal Databricks workspace and is not copied into this report because it contains detailed evidence.

## Recommended next phase

1. Keep production unchanged.
2. Keep `agent_booking_risk_current_poc_v2_v23` as the controlled pilot interface.
3. Tighten the two agent contracts for C01, C03 and C06 so the requested fields and result order are always returned.
4. Enable or capture structured tool and SQL traces that prove the selected source and executed query.
5. Rerun the same 42-trial test as a new version without changing its ground truth.
6. Expand to the remaining question-bank areas only after the booking-scope contract is stable.

Historical-threshold calibration, actual-event enrichment and swap scoring stay parked as separate work.

## One-minute manager version

> I kept production unchanged and built a smaller booking view over a validated personal fact-and-dimension model. I compared it with a frozen wide-table baseline using seven technically cross-checked questions, three times through each agent, for 42 completed responses. The curated path was slightly more accurate, 72.2% versus 66.7% across the C01-C06 table-answer runs. Both paths were stable for three of four comparable question groups, and there was no clear latency winner. Most remaining misses came from output formatting and one unstable ranking case, not a failed table build. My recommendation is to keep the production Gold table, continue with the curated view as a pilot, fix the agent response contract and SQL tracing, then rerun before making any migration decision.

## Related evidence

- [Standalone benchmark visual](csm-csal-v2-controlled-benchmark-visual-2026-09-10.html)
- [Production and V2 architecture](../OBSIDIAN_PRODUCTION_AND_V2.md)
- [Production smoke observations](csm-csal-production-vs-booking-view-smoke-2026-09-09.md)
- [Question bank](../question_bank.md)
- [Current build status](csm-csal-build-watch.md)
