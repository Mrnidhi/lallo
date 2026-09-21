# CSAL Swap Recommendation Timing EDA

## Business question

When should the swap recommendation system alert sales representatives relative to the TCR cutoff, so they still have enough time to review and act?

This EDA looks for candidate intervention windows in historical booking activity. It does not yet measure whether a recommendation was accepted or whether a swap succeeded.

## Analysis flow

1. Start with **228,795 source cases** and identify which records can support cutoff-timing analysis.
2. Separate the **61,347 cases with no booking number** from the **167,448 booking cases** that can enter booking-based matching.
3. Match booking cases using controlled logic:
   - Exact booking-and-TCR match first.
   - Unique-booking fallback only when an exact match is unavailable.
4. Compare the shipment record-creation date with the TCR cutoff date and group pre-cutoff activity into practical day ranges.
5. Use those ranges to form a preliminary hypothesis for a recommendation window.
6. Keep same-day, after-cutoff, and unscorable cases separate from the pre-cutoff recommendation analysis.

## Verified findings

### Matching coverage

- **167,321 of 167,448 booking cases matched**, giving **99.9% coverage among booking cases**.
- **166,213** were exact booking-and-TCR matches.
- **1,108** used the unique-booking fallback.
- **127** cases had a booking number but remained unmatched.
- The main full-source coverage gap is the **61,347 cases with no booking number**.

### Calendar-day timing

- All available TCR cutoffs are **date-only**.
- **163,429 matched cases** have a known calendar-day order.
- **128,266** have a shipment record-creation date before the cutoff date.
- **35,163** have a shipment record-creation date after the cutoff date. This is **21.5% of cases with a known calendar order**.
- **3,892** occur on the same calendar date as the cutoff, so their order is unknown.

### Pre-cutoff activity windows

Of the **128,266 before-cutoff cases**:

- **31+ days:** approximately **4.1K**
- **15–30 days:** approximately **28.68K**
- **8–14 days:** approximately **51.1K**, or **39.8%** of before-cutoff cases
- **4–7 days:** approximately **29.03K**, or **22.6%**
- **1–3 days:** approximately **15.36K**

The **8–14-day** and **4–7-day** windows together contain approximately **62.5%** of observed before-cutoff activity.

## Preliminary conclusion

The **8–14-day window is the strongest starting hypothesis for the first swap recommendation**, because it is the largest observed pre-cutoff activity window at about 39.8% of before-cutoff cases. The **4–7-day window is a candidate final-action or escalation window**, representing another 22.6%. Together, these windows account for approximately 62.5% of observed before-cutoff activity.

This is a timing hypothesis, not a proven recommendation policy. The analysis uses shipment `rec_cre_dt_utc` as a proxy for business booking creation, all cutoffs are date-only, and the current data contains no historical swap recommendation, acceptance, or outcome label. The windows should therefore guide the next validation and experiment rather than be deployed as fixed rules.

## Databricks dashboard built

The draft remains unpublished and has two working pages.

### Recommendation decision

This is the presentation page for the meeting. It contains:

- A direct business question and preliminary answer: first recommendation at **14 days**, then priority or reminder at **7 days**.
- An evidence note that states the timestamp proxy, date-only cutoff limitation, and the difference between historical activity and recommendation impact.
- Four KPI cards: **99.9% controlled match rate**, **167.32K matched booking cases**, **163.43K known-order cases**, and **21.5% observed after the recorded cutoff date**.
- One full-width timing chart ordered as a business timeline: **31+ days, 15–30 days, 8–14 days, 4–7 days, 1–3 days, same day, after cutoff, not scorable**.

### Timing overview

This is the supporting-analysis page. It contains:

- Service-level lead-time box plots.
- Customer and service filters.
- The preliminary recommendation narrative.
- Join-coverage counts for exact, fallback, missing-booking, and unmatched cases.
- Booking-status counts as a supporting operational view.
- The full timing distribution.

The decision page should be shown first. The timing-overview page should be used only when questions arise about service variation, matching quality, or data coverage.

## Charts to remove or repurpose

- Remove a booking-status chart that shows only raw status counts; repurpose it as timing window by booking status.
- Remove pie or donut charts that repeat the coverage or timing counts.
- Remove hour-level lead-time charts because every cutoff is date-only.
- Remove customer or service rankings based only on the after-cutoff percentage; they can mislead when denominators differ and there is no outcome label.
- Remove raw customer-volume charts. Use the customer filter and evidence table instead.
- Do not add maps or unrelated operational charts that do not answer the recommendation-timing question.

## Chart-by-chart speaking story

### Lead time by service

“This chart checks whether one recommendation window can work across services or whether the timing needs to be service-specific. It is exploratory; no service-level result is claimed until the timestamp definition and supporting case counts are validated.”

### Join coverage

“Of 167,448 cases with a booking number, 167,321 matched. Most—166,213—matched exactly on booking and TCR, while 1,108 used the controlled unique-booking fallback. Only 127 booking cases remained unmatched. The larger coverage limitation is the 61,347 source cases without a booking number.”

### Booking timing distribution

“This chart separates **128,266 before-cutoff cases**, **35.16K after-cutoff cases**, **3.89K same-day cases**, and **61.47K cases that are not scorable**. The recommendation-window hypothesis comes only from the before-cutoff population.”

### Pre-cutoff recommendation windows

“The largest observed pre-cutoff window is 8–14 days, with about 51.1K cases or 39.8% of before-cutoff activity. The 4–7-day window contains another 29.03K cases or 22.6%. Together they cover 62.5%, which makes 8–14 days a candidate first-alert period and 4–7 days a candidate final-action period. Historical activity concentration alone does not prove that these are the most effective recommendation times.”

### Booking status

“This chart tests whether the candidate window should depend on booking status. It is a comparison view only; any status-specific recommendation rule would need confirmed definitions, sufficient case counts, and swap outcomes.”

## Limitations

- TCR cutoffs contain dates but no cutoff times, so hour-level timing is unavailable.
- Same-day cases cannot be ordered and must remain a separate category.
- `rec_cre_dt_utc` may represent shipment-record creation rather than the true business booking-creation event.
- Cases without a booking number cannot enter the current controlled booking match.
- The unique-booking fallback is logically constrained but still needs business approval.
- There is no historical label showing whether a swap was recommended, accepted, rejected, or operationally successful.
- Concentrated booking activity does not by itself identify the optimal recommendation time.
- The current analysis identifies timing patterns; it does not establish recommendation effectiveness, cause, operational fault, or policy noncompliance.

## Questions to validate

1. What exact business condition should trigger a swap recommendation: allocation shortfall, low booking, excess demand, or another event?
2. Is 8–14 days enough time for a sales representative to review and act, and when should an unresolved case be escalated?
3. What is a successful recommendation: acceptance, completed swap, improved utilization, reduced shortfall, or another outcome?
4. Does `rec_cre_dt_utc` represent the booking event, and where can the true booking-request timestamp be found?
5. Is a TCR cutoff timestamp and timezone available in another source?
6. Where are historical swap offers, user decisions, and rejection reasons stored?
7. Should recommendation timing vary by service, customer, agreement, booking status, or trade lane?

## Recommended next analysis

1. Obtain the true booking-request or booking-creation timestamp.
2. Obtain the precise TCR cutoff timestamp and timezone, if available.
3. Add historical swap recommendation or offer records with accepted, rejected, expired, and completed outcomes.
4. Add the business result of each recommendation, such as allocation utilization, remaining shortfall, or completed swap volume.
5. Capture historical snapshots of bookings, allocation, and remaining capacity using only information available at each proposed recommendation date.
6. Add swap eligibility constraints and the identifiers needed to construct valid source-and-target swap pairs.
7. Validate the 8–14-day first-alert and 4–7-day escalation hypothesis with Jerlee, then measure acceptance and business impact before training a recommendation model.
