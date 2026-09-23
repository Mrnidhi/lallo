# Individual customer booking and requested-space history

Copy the whole [notebook file](../notebooks/csal-customer-bookings-and-extra-space.py) into one **Python** cell in Databricks inside the Windows VM. It is self-contained; no previous cells need to run. It reads source tables only.

At the top, leave `SERVICES = None` for all services. To start with a particular customer, set:

```python
YEAR = 2026
SERVICES = None
CUSTOMER = "Customer name from your earlier lookup"
CHART_SERVICE = None
AUDIT_TIMEZONE = None
```

Leave `CUSTOMER = None` to calculate all available customers. The first chart will select a customer with both booking and request-edit evidence where available, then prefer the largest included booking history. The selected name and service are printed. All usable customers remain in the summary table.

After the run, change the chart in another Python cell:

```python
show_customer_activity("Customer name", "SERVICE_CODE")
```

The function takes the customer first and service second. Each chart covers one customer and one service. Different company aliases are not merged; capitalization and extra whitespace are normalized.

## Outputs

1. **Booking coverage:** records included in the TCR comparison, and the reasons others could not be used.
2. **Requested-space audit coverage:** positive edits, initial values, decreases, system updates, duplicate/conflicting entries and unresolved customer assignments.
3. **Customer summary:** included booking count, voyages, median booking day, recorded increase count and TEU statistics.
4. **One figure with two panels:** a daily booking-count curve around TCR cutoff, and a stem chart showing the date and added TEU of each qualifying requested-space edit. Each dot in the second panel represents an edit. Overlapping dots can occur; use the event table for exact counts and timestamps.
5. **Exact requested-space edits:** original timestamp, UTC timestamp where supported, plan, available consistent voyage/agreement, previous requested amount, new requested amount, added TEU and editor.
6. **Daily booking counts and booking timestamps:** the exact creation timestamps and matched cutoffs for the selected customer. The detail preview is capped at `MAX_BOOKING_ROWS_SHOWN`; counts and statistics use all included bookings.
7. **Selected-customer booking coverage:** shows how much of this customer's available history supports the booking curve.

## Reading the amounts

An edit from 4 TEU to 7 TEU has **3 added TEU** and a **7 TEU resulting requested total**.

| Summary fields | Meaning |
|---|---|
| `min_extra_teu`, `median_extra_teu`, `max_extra_teu` | Minimum, median and maximum positive increase across individual qualifying edits. |
| `min_requested_total_teu`, `median_requested_total_teu`, `max_requested_total_teu` | Minimum, median and maximum resulting requested totals at those same edits. |
| `recorded_increases` | Number of qualifying audit edits, not distinct customer messages or fulfilled requests. |
| `median_booking_day` | Median days from TCR cutoff for included bookings. Negative is before cutoff. |

For increases of 2, 3 and 8 TEU, the minimum is 2, median is 3, and maximum is 8. These statistics use individual edits, not daily sums. An increase that is later reversed remains a recorded increase; the chart does not measure net demand or fulfilled space.

## What qualifies as an extra-space edit

The code uses positive changes to **`requestedTeu`** in `csal_audit_trail`, recorded as `grid edit` or `multi edit`, with a named editor other than `System`. Both old and new values must be numeric and nonnegative. An initial value from null is not treated as an increase from zero. Finalization, submission, adjusted/reviewed allocation fields and other workflow copies are not added to the count.

This is a recorded increase in requested space. It is **not proof that the customer personally submitted a request**, and it is not necessarily extra space above their approved allocation. For example, a sales representative may enter or correct the value. The code does not claim to identify customer communications or confirmed swaps.

Exact duplicate source rows are removed. Conflicting rows sharing an audit ID, or the same edit appearing under different IDs, are excluded and reported. Customer and service come from available `csal_change_log` history for the plan; they must be consistent across that available history. This does not prove that every historical version is retained. Unattributable histories remain in audit coverage and may fall outside a requested customer/service filter because their identity cannot be resolved.

## Dates and scope

- Booking creation uses `csal_shipment.rec_cre_dt_utc`, confirmed by the user as original booking time. The existing booking rules are preserved: one shipment per booking, latest customer/route, reliable same-leg cutoff, all current shipment statuses, and a complete configurable −56 to +14-day window inside the selected year through run time. Connecting routes and missing or ambiguous stops stay in coverage.
- Requested-space history covers qualifying edits whose **recorded year** is `YEAR`, across all available plans with consistent customer/service identity. It is not limited to the booking curve's voyages or mature-cutoff population. The two panels answer separate parts of the customer's history and must not be treated as a matched booking-to-request sequence.
- Audit timezone is still unconfirmed. Keep `AUDIT_TIMEZONE = None` unless the data owner confirms it. Raw recorded times can be shown without assigning them a UTC timezone. Explicit offsets are retained and can be converted; a confirmed named timezone can also be configured. Ambiguous daylight-saving times remain unresolved.
- If every displayed edit has a resolved UTC timestamp, the edit chart uses UTC. Otherwise it uses the recorded clock values with an explicit label. The exact table preserves each event's time basis.
- Request edits are **not placed on the TCR axis**. That requires the audit timezone and a defensible cutoff for the plan at the event time, which the current evidence does not establish. Confirming a timezone alone does not supply that cutoff.
- No qualifying edits means no qualifying evidence was found. It does not mean the customer asked for no extra space. Quantity statistics remain empty, rather than becoming zero.

Dependencies: Spark, pandas, NumPy and Matplotlib. The cell does not install packages or change compute settings. It stops rather than returning partial statistics if the audit-row or customer-summary limits are exceeded; narrow `CUSTOMER` or `SERVICES` and rerun.

Validation uses synthetic SQL and chart cases locally. A live Databricks run is still needed to obtain the actual customer results.
