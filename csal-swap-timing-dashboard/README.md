# CSAL timing and allocation dashboard

For notebook charts, copy [the single-cell notebook code](notebooks/csal-three-charts-cell.py) into one Databricks notebook cell and run it. It produces the daily cutoff curve, cumulative curve, and allocation revisions by weekday.

For the dashboard version, use [the complete dashboard build guide](docs/CSAL_DASHBOARD_COMPLETE_BUILD.md).

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

Shipment-record creation has not been confirmed as original customer booking
time. Current routes and cutoffs are not historical snapshots. Recorded
allocation revisions are not confirmed swaps. The evidence does not yet
establish a recommendation day.

Other SQL files, notebooks, diagrams and presentation notes in this folder are
earlier investigation material. They may use different populations, matching
rules, or provisional interpretations. Follow the complete build guide for the
current dashboard; earlier suggested alert dates are hypotheses, not validated
business rules.
