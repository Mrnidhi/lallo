# CSAL Swap Recommendation Timing Dashboard

This folder contains the current preliminary analysis package for deciding when a swap recommendation could be shown before the recorded TCR cutoff.

## Contents

- `sql/csal_tcr_tiered_match_v2.sql` — Databricks SQL that creates the case-level matching and timing dataset.
- `docs/CSAL_EDA_STORY.md` — business question, verified findings, dashboard structure, limitations, and next analysis.
- `docs/CSAL_DASHBOARD_PRESENTATION_SCRIPT.md` — full presentation script, 30-second version, KPI definitions, and likely questions.
- `erd/csal-booking-cutoff-logical-erd-standard.drawio` — editable logical ER diagram.
- `erd/csal-booking-cutoff-logical-erd-standard.{png,pdf,svg}` — presentation-ready ERD exports.
- `erd/render-csal-logical-erd-standard.py` — local source used to regenerate the ERD exports.

## Current analytical scope

The SQL combines:

- `dev.crmi_gold.csal_teu_performance_nrt` for the latest NRT booking case and recorded TCR cutoff.
- `datasources.csal.csal_shipment` for the shipment record-creation timestamp and candidate TCR fields.

It retains unmatched cases, distinguishes exact and controlled fallback matches, and calculates calendar days before the recorded cutoff. The current 14-day first-alert and 7-day escalation points are preliminary hypotheses based on historical timing concentration.

## Interpretation limits

- `rec_cre_dt_utc` is treated as a shipment record-creation proxy and still needs business confirmation as the correct booking event.
- Observed TCR cutoffs are date-only, so same-day ordering and exact hour-level timing are unavailable.
- The current data does not contain recommendation, acceptance, completed-swap, or business-outcome labels.
- Aggregate results in the documents reflect the analyzed snapshot and should be refreshed after rerunning the SQL on newer data.
