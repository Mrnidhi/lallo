# CSAL Swap Recommendation Timing Dashboard — Presentation Script

## How to present it

Open the **recommendation decision** page first. Use the **timing overview** page only if Jerlee asks about matching, service variation, booking status, or data coverage.

## Main script

“Today I am presenting a preliminary EDA for the planned swap recommendation system.

The business question is: **when should we show a swap recommendation to a sales representative before the recorded TCR cutoff, so there is still enough time to review and act?**

For this first analysis, I built a timeline by connecting two sources. The NRT performance table provides the booking number, customer, service, TCR, booking status, and recorded TCR cutoff. The CSAL shipment table provides `rec_cre_dt_utc`, which I am currently using as a proxy for booking creation time. I then calculate how many calendar days each observed shipment record was created before or after its recorded cutoff.

The analysis dataset contains **228,795 case-level records**. Of these, **167,448 have a booking number** and can enter booking-level matching. The remaining **61,347 have no booking number**, so I kept them as not scorable instead of forcing an uncertain join.

I used controlled matching in two steps. First, I matched the normalized booking number and NRT TCR against the shipment TCR fields. That produced **166,213 exact matches**. When an exact TCR match was unavailable, I used a booking-only fallback only where all matching shipment rows contained exactly one distinct non-null creation timestamp. That added **1,108 matches**. Overall, **167,321 of 167,448 booking cases matched**, which is a **99.9 percent coverage rate among booking-present cases**. Only **127 booking-present cases remained unmatched. The coverage is strong, while the timestamp meaning and fallback rule still need business validation.**

[Point to the KPI cards.]

These cards summarize the usable population. The 99.9 percent is the controlled match rate among cases that contain a booking number. The 167.32K card is the number of matched booking cases. The 163.43K card is the number whose creation date can be clearly ordered before or after the cutoff date. Same-day cases are excluded from that ordered number because no confirmed intraday cutoff time is available. The 21.5 percent card means **35,163 cases were observed after the recorded cutoff date** out of the 163,429 cases with a known before-or-after order.

[Point to the timeline chart.]

The chart shows the complete population in business time order. The main recommendation evidence comes only from the **128,266 cases observed before cutoff**.

Within that pre-cutoff population, the largest window is **8 to 14 days before cutoff**, with about **51.1K cases**, or **39.8 percent**. The next important window is **4 to 7 days before cutoff**, with about **29.03K cases**, or **22.6 percent**. Together, these windows contain **80,130 cases**, equal to **62.5 percent of all observed pre-cutoff activity**.

Based on this pattern, my preliminary proposal is to **begin at day 14**, when a case enters the 8-to-14-day candidate window. This gives the sales representative time to review it. If the opportunity is still unresolved, the system can **raise its priority or send a reminder at day 7**, when it enters the 4-to-7-day candidate window. These exact checkpoints are an operational translation of the broader observed windows; they are not empirically proven optimal days.

This is a practical starting hypothesis, not a proven production rule. The current analysis tells us **when historical activity is concentrated**. It does not yet tell us whether a recommendation sent on a particular day will be accepted or will produce a successful swap.

There are three important limitations. First, no confirmed intraday cutoff time or timezone is available, so I can compare calendar days but not exact hours. Second, `rec_cre_dt_utc` is a UTC shipment-record creation timestamp and still needs confirmation as the correct business booking event. Third, the current data has no recommendation, acceptance, completed-swap, or business-outcome label.

The **35,163 after-cutoff observations are therefore a data and process signal to investigate**. I would not call them late bookings or violations until we validate the cutoff definition, timezone, and true booking-event timestamp.

My next step is to confirm the timestamp definitions with the business team, add the true booking or request event if available, and connect the recommendation and swap outcomes. Then we can test whether the 14-day first alert and 7-day escalation actually improve acceptance, completed swaps, allocation utilization, or shortfall.

So the preliminary conclusion is: **start with a recommendation at 14 days before the recorded TCR cutoff and increase urgency at 7 days. Treat these as candidate intervention points for validation, because the current dashboard establishes a historical timing pattern rather than recommendation impact.**”

## If you need a 30-second version

“I built a preliminary timeline to identify when swap recommendations could be shown before the recorded TCR cutoff. Of 167,448 cases with booking numbers, 167,321 matched through controlled logic, giving 99.9 percent coverage. Among 128,266 pre-cutoff cases, 62.5 percent occurred between 4 and 14 days before cutoff. My current hypothesis is therefore a first alert at 14 days and a priority reminder at 7 days. This still needs validation because the shipment creation timestamp is a proxy, no confirmed intraday cutoff time is available, and we do not yet have recommendation or swap-outcome labels.”

## Exact meanings to remember

- **228,795 analysis cases:** case-level population after the dashboard's distinct/latest-snapshot logic.
- **167,448 booking cases:** analysis cases containing a booking number.
- **167,321 matched:** 166,213 exact booking-and-TCR matches plus 1,108 controlled fallback matches.
- **99.9% match rate:** 167,321 divided by 167,448; it is not the match rate over all source cases.
- **61,347 missing booking numbers:** cannot be safely joined at booking level with the current keys.
- **127 unmatched booking cases:** booking number exists, but no controlled match was accepted.
- **61,474 not scorable:** 61,347 missing-booking cases plus 127 unmatched booking cases.
- **163,429 known-order cases:** matched cases clearly before or after cutoff; excludes 3,892 same-day cases.
- **128,266 before cutoff:** population used to derive the recommendation windows.
- **35,163 after recorded cutoff:** 21.5% of known-order cases; a signal to investigate, not proof of lateness.
- **80,130 in the 4–14-day range:** 62.5% of the before-cutoff population.

## Likely questions and direct answers

**Why did you choose 14 days and 7 days?**

The 8–14-day window is the largest observed pre-cutoff window, and the 4–7-day window is the next major window. Together they contain 62.5 percent of pre-cutoff observations. Fourteen and seven days are simple operational checkpoints at the start of those windows.

**Does the dashboard prove that these are the best send dates?**

No. It identifies candidate dates from historical timing concentration. Proving effectiveness requires recommendation and outcome data or a controlled pilot.

**Why not match the records without booking numbers using customer or service?**

Those fields are not unique enough for a safe record-level join. Keeping the cases unscored avoids false matches.

**How strong is the matching coverage?**

Among cases with a booking number, 99.9 percent matched. Most were exact booking-and-TCR matches; the fallback was allowed only when all shipment rows for that booking had one distinct non-null creation timestamp. This shows strong coverage, while business validation is still required to confirm correctness.

**What does “after cutoff” mean?**

It means the proxy creation date is later than the recorded cutoff date. It does not yet mean a violation, because the precise cutoff time and timezone are unconfirmed and the proxy timestamp may not be the true booking event.

**Which tables are used in this dashboard?**

`dev.crmi_gold.csal_teu_performance_nrt` supplies the NRT booking and cutoff fields. `datasources.csal.csal_shipment` supplies the shipment record-creation timestamp and matching TCR fields.

**Where does the audit-trail table fit?**

This first dashboard establishes the booking-to-cutoff timing baseline. The audit trail can be added next to place requested, adjusted, submitted, accepted, and finalized CSAL events on the same timeline once its `csal_id` is connected to the required business keys.

**What should be done next?**

Confirm the real booking-event timestamp and exact cutoff timestamp, add the CSAL event journey, obtain swap recommendation and outcome records, then validate the 14-day and 7-day hypothesis by service and through a controlled pilot.

## One sentence to avoid overclaiming

Say: **“This is the strongest historical timing hypothesis in the current data.”**

Do not say: **“The analysis proves that 14 days is the optimal recommendation time.”**
