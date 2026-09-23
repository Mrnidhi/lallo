# CSAL timing and allocation dashboard

## Customer booking patterns — current analysis

Use [the complete customer-pattern notebook](notebooks/customer-booking-patterns/customer_booking_patterns_all_in_one.py)
for the current question: when each customer usually books relative to TCR cutoff,
and which customers share similar habits within each service. It calculates all
services, keeps low-history customers visible, and produces the customer lookup
and two focused charts. See [paste instructions and settings](notebooks/customer-booking-patterns/README.md).

The user confirmed `csal_shipment.rec_cre_dt_utc` as original booking time on
September 23, 2026. This new notebook uses that definition. Customer names are
used as the requested identity proxy, with case and whitespace normalization.
Current routes and cutoffs still do not reconstruct historical schedule changes.

## Earlier notebook and dashboard work

For notebook charts, copy [the single-cell notebook code](notebooks/csal-three-charts-cell.py) into one Databricks notebook cell and run it. It produces the daily cutoff curve, cumulative curve, and allocation revisions by weekday.

For the dashboard version, use [the complete dashboard build guide](docs/CSAL_DASHBOARD_COMPLETE_BUILD.md).

## Customer request timeline

Copy [the request timeline cell](notebooks/csal-customer-request-timeline-cell.py)
into one Databricks notebook cell. Set `TARGET_SVVD` to the full
service-vessel-voyage and direction from your data, then run it. Set `CUSTOMER`
only if you want one exact customer name. The chart shows up to 25 shipments;
the accompanying table includes the complete selected cohort up to the stated cap.

This version treats a space request as an external customer booking request.
It reads `request_submission_date` from `csal_shp_external_rqst`, checks direct
shipment links and reference candidates, and compares available submission
values with `csal_shipment.rec_cre_dt_utc`. It does not infer links from names.
That earlier cell labels the red marker **shipment-record creation**; it predates
the user's confirmation used in the customer-pattern notebook. Blue markers show the earliest
available timed request per shipment, which can be an amendment and is not
proof of the first request ever made. Current vessel assignment may differ
from assignment when either timestamp was recorded.

Keep `REQUEST_TIMEZONE = None` unless the field's timezone is confirmed.
Timestamps with explicit offsets can be plotted immediately. Unzoned values,
conflicting routes/dates, reference-only links, and ambiguous shipment links
remain in the results table instead of being guessed. Missing requests do
not become zero waiting time. A CSAL allocation request is a different event
and is not represented by this cell.

The cell uses session-local temporary data and reads source tables only. It
was checked locally with synthetic data; a live Databricks run is still needed.
Timestamp conversion requires an explicit offset or a known timezone; see
[Databricks timestamp guidance](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_utc_timestamp).


That single Markdown file contains:

- Where to paste two independent, read-only Databricks SQL queries.
- All-service shipment timing relative to the latest available TCR cutoff.
- Daily and cumulative line-chart settings, including the correct day-zero boundary.
- Recorded allocation revisions, shown by calendar date or weekday.
- Service filters, coverage tables, reconciliation checks, and editable date settings.
- The evidence still needed to establish actual swap timing and a recommendation window.

The guide uses `datasources.csal.csal_booking_detail`, `csal_shipment`,
`csal_voy_stop_dtl`, and `csal_change_log`. It does not depend on CRMI tables or
temporary notebook views. Access corporate systems through the Windows VM.

## Interpretation

The earlier notebooks retain their original provisional record-creation labels;
the customer-pattern notebook above incorporates the user's later confirmation.
Current routes and cutoffs are not historical snapshots. Recorded
allocation revisions are not confirmed swaps. The evidence does not yet
establish a recommendation day.

Other SQL files, notebooks, diagrams and presentation notes in this folder are
earlier investigation material. They may use different populations, matching
rules, or provisional interpretations. Follow the complete build guide for the
current dashboard; earlier suggested alert dates are hypotheses, not validated
business rules.
