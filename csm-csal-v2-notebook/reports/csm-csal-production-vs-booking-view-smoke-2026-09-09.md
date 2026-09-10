# Production main agent vs booking-scope view: C01 smoke test

Date: 9 September 2026

> **Historical smoke evidence:** preserve this dated observation as recorded. It is not part of the completed controlled A/B score. See [the final C01-C07 result](csm-csal-v2-controlled-benchmark-results-2026-09-10.md) for the current decision.

## Purpose

Compare the existing production Sales Chat main agent with the personal V2 booking-scope supervisor using the same verified C01 wording. This was a question-only observation. No production settings, code, data, routes or tables were changed.

## Question

> For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations with the lowest confirmed utilization of their total reviewed commitment. Include confirmed TEU, total reviewed commitment and the utilization percentage. Only include combinations where the percentage can be calculated.

## Observed result

| System | Outcome |
|---|---|
| Existing production `agent-sales-chat` app | Returned no business rows. Its final message said the data request had been retried twice and no rows were returned. |
| Personal `sales-ai-booking-scope-v2` supervisor | Routed to `CSM Booking Scope V2` and returned the expected 20-row customer + agreement + TCR table with confirmed TEU, total reviewed commitment and utilization. The visible rows and ordering matched the already verified C01 booking-view result. |

## Interpretation

For this one question, the curated booking-view path succeeded while the production main-agent path did not retrieve a result. This supports investigating production routing or retrieval for this question pattern. It does not prove that the production data is wrong, that production always fails, or that the full dim/fact design is better for every question.

## Evidence limits

- This was one manual UI observation, not a repeated benchmark.
- Production performed its own two retries; we did not submit another production request.
- Exact end-to-end timings were not captured with a common timer.
- Production SQL, selected specialist and source table were not visible in the final response, so they remain unverified.
- The personal result is a second UI observation; the controlled notebook already recorded its earlier C01 run separately.
- No customer rows, credentials or tokens are stored in this local note.

## Recommended next step

Repeat the same question two more times only if a production-observation series is approved, then test the next verified booking questions. Keep those observations in a separate evidence set from the personal A/B benchmark. Investigate routing and retrieval before proposing production changes.

## Hard-scenario wording pilot

A first draft of H01 was also asked once in each UI. Both systems returned a 10-row low-utilization answer, but the visible cancellation and rejection flag summaries disagreed. The draft wording had not explicitly excluded rows where utilization could not be calculated, and the production answer selected NULL-utilization rows. This run is therefore a wording pilot, not a scored production comparison.

The question was corrected in `v2_hard_sales_rep_2` to say “where that utilization can be calculated.” No business row values are stored in this note. The corrected question still needs an independently verified answer before scoring.

## Multi-source freshness pilot

H14 was submitted once to the personal booking-view main agent in a fresh Playground conversation. The supervisor consulted several specialists and correctly discovered that the booking view does not expose the requested source-date field. It then remained on a later specialist call for more than four minutes without producing a final answer.

This is recorded as an incomplete orchestration and latency observation. It was not retried, and the production main agent was not sent an unmatched H14 request. The outcome does not show a table failure; it shows that a broad multi-specialist question can be slow or stall even when the individual sources are readable.

## Corrected H01 matched observation

The corrected `v2_hard_sales_rep_2` wording was then asked once in a fresh production conversation and once in a fresh personal booking-view Playground conversation.

| Observation | Production main agent | Personal booking-view main agent |
|---|---:|---:|
| Rows returned | 10 | 10 |
| High-cancellation flags reported | 8 | 7 |
| High-rejection flags reported | 0 | 2 |
| Confirmed-utilization range reported | 0.00% to 4.76% | All 10 at 0.00% |

The two systems therefore returned different populations or values for the same business wording. This is not yet a correctness verdict because the production source, route and data timestamp were not exposed, while the personal answer identified the frozen `CSM Booking Scope V2` route. The result may reflect routing, source version, data freshness, formula or query differences. Independently verified reference data is required before calling either answer correct.

No row-level customer values are stored locally.

## 2026-09-09 ground-truth checkpoint

The direct H01 reference calculation is now independently checked: 10 rows were selected under the stated deterministic order. All ten had fulfillment_pct equal to 0; six carried the stored high-cancellation flag and two carried the stored high-rejection flag. The direct SQL completed in approximately 0.06–0.08 seconds. Under this deterministic reference, the earlier production result of 8/0 and personal result of 7/2 are both incorrect, although the personal result was closer on the flag counts.

H04 was independently checked at its two intended grains. The booking/TCR result contains four rows with confirmed TEU summing to 4 and booked TEU summing to 8. The commitment result contains one row with total_reviewed_teu equal to 4. Keeping these outputs separate confirms that the commitment is not repeated once per TCR.

The formal benchmark remains at 2 of 72 planned trials, and the next controlled pair is C02. These checks establish reference evidence only; they do not add a production comparison result.

## H09 cross-specialist morning briefing

H09 was asked once in a fresh conversation on both sides using the same representative, week and service. It tested whether the main agent could assemble booking risk, finance, cases and the current Daily Outlook while keeping the four sources separate.

| Requirement | Production main agent | Personal booking-view main agent |
|---|---|---|
| Booking section | Returned | Returned after an unsafe retry |
| Finance section | Returned | Returned |
| Cases section | Missing from final answer | Returned |
| Current Daily Outlook | Missing from final answer | Returned |
| Four clearly separate sections | No | Yes |
| Source and available data time for every section | No | Partial |
| Representative-scoped booking rows proven | Not visible | No |

The personal CSM reader first returned an empty result when asked to filter booking risk by the representative. The supervisor then retried the booking request without that filter and presented general booking rows inside a representative-specific briefing. This is unsafe scope fallback. The current `agent_booking_risk_current` view is built at customer, agreement, reporting week, service and TCR level and does not carry a verified sales-representative relationship.

Production produced a shorter response and included booking and finance findings, but its final answer omitted the requested cases, Daily Outlook, source separation and freshness information. Its actual CSM route and representative filtering were not visible, so those remain unverified.

The correct next design step is not to add a sales field casually to the booking view. First prove how a sales representative maps to a booking scope and whether that relationship is one-to-one, one-to-many or effective-dated. Then expose a separate portfolio-safe view or bridge and retest H09. No production change is justified from this single observation.

## H04 mixed-grain observation

H04-A was asked once in fresh conversations on both sides. The fixture had four TCR booking rows under one customer, agreement, week and service scope. No customer or agreement values are stored in this note.

| Check | Production main agent | Personal booking-view main agent |
|---|---|---|
| TCR-level confirmed and booked TEU | Returned four TCR rows | Returned four TCR rows |
| Reviewed commitment shown once at its four-key scope | No | Yes |
| Reviewed commitment attached to individual TCR rows | Yes | No in the final business answer |
| Followed the requested mixed-grain presentation | No | Yes |

The personal answer kept the booking measures at customer, agreement, week, service and TCR grain, then presented the reviewed commitment once at customer, agreement, week and service grain. Production attached reviewed commitment values to the TCR lines and described the total ambiguously. This is the legacy wide-table presentation pattern, not proof that commitment is truly a TCR-level measure.

This observation supports the reason for separating booking and commitment facts and hiding the relationship behind a curated view. It does not prove that the underlying production data is wrong, and the numerical value has not been independently certified for this manual fixture. H04 should be scored against the mixed-grain contract after the reference result is independently verified.

## C02 production main-agent smoke observation

On 10 September 2026, the exact verified C02 wording was submitted once in a fresh production `agent-sales-chat` conversation. The agent completed in roughly 35 seconds and said that it found 20 low-booking combinations for week `2026WK22` and service `PVCS`.

The final response summarized the population and mentioned a few examples, but it did not display the requested 20-row result with all customer, agreement, TCR, confirmed TEU, booked TEU and total reviewed commitment columns. The visible response also did not identify the selected specialist, source table or SQL. There was no visible retry or error.

For this smoke observation, the outcome is `PARTIALLY_SUPPORTED`: the agent understood the filter and returned a business summary, but the requested detailed result shape was not shown. This is not part of the controlled personal A/B score. No customer names or row-level values from the response are stored here.
