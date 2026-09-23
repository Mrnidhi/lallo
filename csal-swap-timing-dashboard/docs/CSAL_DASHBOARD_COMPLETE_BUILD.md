# CSAL dashboard: timing around TCR cutoff and allocation changes

## Start here: where to paste the code

Use **Databricks inside the Windows VM**. Paste the SQL into the dashboard's **Data** tab, not a Python notebook cell, a chart prompt, or a terminal.

1. Open the existing dashboard, **csal booking timing around tcr cutoff**.
2. Click **Data**. Open the dataset currently feeding the daily shipment chart. Replace its SQL with **Dataset A** below and click **Run**. Reusing that dataset preserves its chart connections. If starting fresh, add a SQL dataset and name it `shipment_timing`.
3. Add a second SQL dataset, name it `allocation_revisions`, paste **Dataset B**, and click **Run**.
4. Return to the dashboard page. Follow the filter and chart instructions below in order.
5. Inspect the draft before clicking **Publish**. Use the intended existing audience; there is no need to change sharing permissions.

**There are two SQL blocks to run.** Each is one complete, read-only query. They do not depend on earlier notebook cells, Python variables, temporary views, or a writable schema. They do not create or update source tables. Source scans may take time; let each finish rather than repeatedly running it.

```text
Dashboard > Data
  ├─ Dataset A: shipment timing ── daily curve + cumulative curve + coverage table
  └─ Dataset B: allocation revisions ── weekday changes + revision coverage table
                     ↓
             One service selector
                     ↓
       Check the draft → publish the dashboard
```

## What this dashboard can answer

- When shipment records appear relative to the latest available TCR cutoff, across available services.
- When finalized allocation amounts are recorded as increasing or decreasing.
- How much source data supports each chart and how much is excluded.

**The second analysis is currently a calendar timeline, not a swap timeline relative to cutoff.** The data supplied so far does not establish the historical cutoff for each allocation change or the audit timestamp's timezone. A convincing-looking cutoff curve would not resolve those gaps.

Shipment-record creation is also not yet confirmed as original customer booking time. Use **shipment records**, **allocation revisions**, and **candidate movements** in titles until those definitions are confirmed. No fixed recommendation day is established by these charts.

## Settings you can change

Change these values at the top of the relevant SQL block, then run that dataset again.

| Setting | Default | Meaning |
|---|---|---|
| A: `as_of_utc` | `CURRENT_TIMESTAMP()` | Query-time boundary. For a fixed report, replace with a UTC timestamp literal such as `CAST('YYYY-MM-DDTHH:MM:SSZ' AS TIMESTAMP)`, using your actual reporting time. |
| A: `first_detail_utc` | 2026-05-01 | Start date for the latest booking-detail record's creation timestamp. This is not a booking-date filter. |
| A: `first_cutoff_utc` | 2026-06-01 | Earliest cutoff included. |
| B: `first_recorded_date` | 2026-06-01 | Earliest recorded allocation-change calendar date. |
| B: `last_recorded_date` | `CURRENT_DATE()` | Last recorded calendar date included. Use `DATE 'YYYY-MM-DD'` for a fixed report. |
| Service | Dashboard selector | Choose any available service or the literal `ALL SERVICES`. No service is hard-coded. |

The date defaults continue the existing dashboard setup; they do not prove that every source is complete from those dates. A fixed reporting timestamp does not recover earlier source versions. The queries always read currently available rows.

Keep the **28 days before / 14 days after** window unchanged for this build. Dataset A requires at least 14 elapsed days since cutoff and counts records from day -28 through day +13. That gives a complete 14-day period after cutoff. Elapsed time alone does not verify source freshness. Changing the window requires changing the maturity condition, bucket range, grid, chart labels, and descriptions together.

## Dataset A — shipment timing

Paste this entire block into the shipment dataset SQL editor and run it once.

This is a conservative same-leg analysis: the first loading SVVD and port must match the corporate SVVD and loading port. Transshipment and conflicting routes remain in coverage counts but are excluded from the timing curves. Exact service/vessel/voyage/direction and loading port must identify one unambiguous current stop. There is no relaxed voyage or port matching.

Booking sail week is retained when checking conflicting detail rows; no equality between plan week and stop week is assumed. This query does not independently validate historical sail-week equivalence. It excludes repeated/ambiguous stop records rather than guessing the port call.

```sql
-- Read-only dashboard dataset. One latest-detail shipment contributes at most one record.
-- rec_cre_dt_utc is CSAL shipment-record creation, not a confirmed customer booking time.
-- Route and TCR cutoff are the latest available values, not historical snapshots.
WITH params AS (
  SELECT CURRENT_TIMESTAMP() AS as_of_utc,
         CAST('2026-05-01T00:00:00Z' AS TIMESTAMP) AS first_detail_utc,
         CAST('2026-06-01T00:00:00Z' AS TIMESTAMP) AS first_cutoff_utc
),
detail_raw AS (
  SELECT
    NULLIF(UPPER(TRIM(CAST(shipment_num AS STRING))), '') AS shipment_num,
    NULLIF(UPPER(TRIM(CAST(corp_svc_cde AS STRING))), '') AS service,
    NULLIF(UPPER(TRIM(CAST(corp_vsl_cde AS STRING))), '') AS corp_vessel,
    NULLIF(UPPER(TRIM(CAST(corp_voy_num AS STRING))), '') AS corp_voyage,
    NULLIF(UPPER(TRIM(CAST(corp_voy_dir AS STRING))), '') AS corp_direction,
    NULLIF(UPPER(TRIM(CAST(lpol_port_cde AS STRING))), '') AS loading_port,
    NULLIF(UPPER(TRIM(CAST(fpol_port_cde AS STRING))), '') AS first_port,
    NULLIF(UPPER(TRIM(CAST(f_load_svc_cde AS STRING))), '') AS first_service,
    NULLIF(UPPER(TRIM(CAST(f_load_vsl_cde AS STRING))), '') AS first_vessel,
    NULLIF(UPPER(TRIM(CAST(f_load_voy_num AS STRING))), '') AS first_voyage,
    NULLIF(UPPER(TRIM(CAST(f_load_dir AS STRING))), '') AS first_direction,
    NULLIF(UPPER(TRIM(CAST(sail_week AS STRING))), '') AS detail_sail_week,
    TRY_CAST(rec_cre_dt_utc AS TIMESTAMP) AS detail_record_created_at,
    COALESCE(TRY_CAST(rec_upd_dt_utc AS TIMESTAMP),
             TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS detail_updated_at
  FROM datasources.csal.csal_booking_detail
  WHERE shipment_num IS NOT NULL
),
detail_routes AS (
  SELECT *,
    CASE WHEN service IS NOT NULL AND corp_vessel IS NOT NULL
               AND corp_voyage IS NOT NULL
               AND SUBSTRING(corp_direction, 1, 1) IN ('N', 'S', 'E', 'W')
      THEN CONCAT(REGEXP_REPLACE(service, '-[NSEW]$', ''), '-',
                  corp_vessel, '-',
                  CASE WHEN LENGTH(corp_voyage) < 3
                    THEN LPAD(corp_voyage, 3, '0') ELSE corp_voyage END,
                  ' ', SUBSTRING(corp_direction, 1, 1)) END AS corp_svvd,
    CASE WHEN first_service IS NOT NULL AND first_vessel IS NOT NULL
               AND first_voyage IS NOT NULL
               AND SUBSTRING(first_direction, 1, 1) IN ('N', 'S', 'E', 'W')
      THEN CONCAT(REGEXP_REPLACE(first_service, '-[NSEW]$', ''), '-',
                  first_vessel, '-',
                  CASE WHEN LENGTH(first_voyage) < 3
                    THEN LPAD(first_voyage, 3, '0') ELSE first_voyage END,
                  ' ', SUBSTRING(first_direction, 1, 1)) END AS first_svvd
  FROM detail_raw
),
detail_ranked AS (
  SELECT *, DENSE_RANK() OVER (
    PARTITION BY shipment_num ORDER BY detail_updated_at DESC NULLS LAST
  ) AS current_rank
  FROM detail_routes
  WHERE shipment_num IS NOT NULL
),
detail_one AS (
  SELECT shipment_num,
    MAX(service) AS service,
    MAX(corp_svvd) AS corp_svvd,
    MAX(first_svvd) AS first_svvd,
    MAX(loading_port) AS loading_port,
    MAX(first_port) AS first_port,
    MIN(detail_record_created_at) AS detail_record_created_at,
    COUNT(DISTINCT detail_record_created_at) AS detail_creation_values,
    SUM(CASE WHEN detail_record_created_at IS NULL THEN 1 ELSE 0 END)
      AS detail_missing_creation_rows,
    COUNT(DISTINCT CONCAT_WS('||',
      COALESCE(service, '<null>'), COALESCE(corp_svvd, '<null>'),
      COALESCE(first_svvd, '<null>'), COALESCE(loading_port, '<null>'),
      COALESCE(first_port, '<null>'), COALESCE(detail_sail_week, '<null>')
    )) AS current_route_variants
  FROM detail_ranked
  WHERE current_rank = 1
  GROUP BY shipment_num
),
shipment_one AS (
  SELECT NULLIF(UPPER(TRIM(CAST(shipment_number AS STRING))), '') AS shipment_num,
    MIN(TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS record_created_at,
    COUNT(DISTINCT TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS distinct_creation_times,
    SUM(CASE WHEN TRY_CAST(rec_cre_dt_utc AS TIMESTAMP) IS NULL THEN 1 ELSE 0 END) AS missing_creation_rows
  FROM datasources.csal.csal_shipment
  WHERE shipment_number IS NOT NULL
  GROUP BY NULLIF(UPPER(TRIM(CAST(shipment_number AS STRING))), '')
),
stop_raw AS (
  SELECT CAST(id AS STRING) AS stop_id,
    COALESCE(NULLIF(UPPER(TRIM(CAST(msg_business_key AS STRING))), ''),
             CONCAT('ID:', CAST(id AS STRING))) AS stop_identity,
    NULLIF(UPPER(TRIM(CAST(port_code AS STRING))), '') AS stop_port,
    CASE WHEN use_dep_svvd = TRUE
           THEN NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST(dep_svvd AS STRING))), ' +', ' '), '')
         WHEN use_dep_svvd = FALSE
           THEN NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST(arr_svvd AS STRING))), ' +', ' '), '')
    END AS effective_svvd,
    TRY_CAST(tcr_cutoff_date AS TIMESTAMP) AS cutoff_ts,
    CASE WHEN is_load_allowed = TRUE AND is_omitted = FALSE
               AND is_tentative_schedule = FALSE AND is_vms = FALSE
               AND is_phase_out = FALSE AND private_call = FALSE
      THEN 1 ELSE 0 END AS stop_flags_ok,
    COALESCE(TRY_CAST(rec_upd_dt_utc AS TIMESTAMP),
             TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS stop_updated_at
  FROM datasources.csal.csal_voy_stop_dtl
),
stop_ranked AS (
  SELECT *, DENSE_RANK() OVER (
    PARTITION BY stop_identity ORDER BY stop_updated_at DESC NULLS LAST
  ) AS current_rank
  FROM stop_raw
),
stop_current AS (
  SELECT *, COUNT(*) OVER (PARTITION BY stop_identity) AS current_stop_rows
  FROM stop_ranked
  WHERE current_rank = 1
),
matched AS (
  SELECT d.shipment_num, d.service, d.corp_svvd, d.first_svvd,
    d.loading_port, d.first_port, d.current_route_variants,
    d.detail_record_created_at, d.detail_creation_values, d.detail_missing_creation_rows,
    sh.record_created_at, sh.distinct_creation_times, sh.missing_creation_rows,
    COUNT(DISTINCT s.stop_identity) AS exact_stops,
    COUNT(DISTINCT s.stop_id) AS exact_stop_rows,
    MAX(s.current_stop_rows) AS max_stop_revision_rows,
    COUNT(DISTINCT s.cutoff_ts) AS distinct_cutoffs,
    MAX(s.cutoff_ts) AS cutoff_ts,
    MAX(CASE WHEN s.stop_identity IS NOT NULL AND s.stop_flags_ok = 0
      THEN 1 ELSE 0 END) AS flagged_stop
  FROM detail_one d
  LEFT JOIN shipment_one sh ON sh.shipment_num = d.shipment_num
  LEFT JOIN stop_current s ON s.effective_svvd = d.corp_svvd
                          AND s.stop_port = d.loading_port
  GROUP BY d.shipment_num, d.service, d.corp_svvd, d.first_svvd,
    d.loading_port, d.first_port, d.current_route_variants,
    d.detail_record_created_at, d.detail_creation_values, d.detail_missing_creation_rows,
    sh.record_created_at, sh.distinct_creation_times, sh.missing_creation_rows
),
scoped AS (
  SELECT m.*, p.as_of_utc, p.first_cutoff_utc,
    CAST(FLOOR((UNIX_MICROS(m.record_created_at) - UNIX_MICROS(m.cutoff_ts))
               / 86400000000.0) AS INT) AS day_from_cutoff
  FROM matched m CROSS JOIN params p
  WHERE m.detail_record_created_at BETWEEN p.first_detail_utc AND p.as_of_utc
     OR m.detail_record_created_at IS NULL
),
classified AS (
  SELECT *,
    CASE
      WHEN current_route_variants <> 1 OR detail_creation_values <> 1
        OR detail_missing_creation_rows > 0 THEN 'ROUTE_OR_DETAIL_TIME_UNRESOLVED'
      WHEN corp_svvd IS NULL OR first_svvd IS NULL
        OR loading_port IS NULL OR first_port IS NULL THEN 'MISSING_ROUTE_FIELDS'
      WHEN first_svvd <> corp_svvd OR first_port <> loading_port
        THEN 'OUTSIDE_SAME_LEG_SCOPE'
      WHEN record_created_at IS NULL OR distinct_creation_times <> 1
        OR missing_creation_rows <> 0 OR record_created_at > as_of_utc
        THEN 'SHIPMENT_CREATION_UNRESOLVED'
      WHEN exact_stops = 0 THEN 'NO_EXACT_STOP'
      WHEN exact_stops <> 1 OR exact_stop_rows <> 1
        OR max_stop_revision_rows <> 1 THEN 'AMBIGUOUS_STOP'
      WHEN flagged_stop <> 0 THEN 'STOP_FLAGS_REQUIRE_REVIEW'
      WHEN distinct_cutoffs <> 1 OR cutoff_ts IS NULL THEN 'CUTOFF_UNRESOLVED'
      WHEN cutoff_ts < first_cutoff_utc THEN 'CUTOFF_BEFORE_SELECTED_START'
      WHEN cutoff_ts > as_of_utc - INTERVAL 14 DAYS THEN 'INSUFFICIENT_FOLLOWUP'
      WHEN day_from_cutoff NOT BETWEEN -28 AND 13 THEN 'OUTSIDE_DISPLAY_WINDOW'
      ELSE 'IN_WINDOW'
    END AS result_status
  FROM scoped
),
coverage AS (
  SELECT CASE WHEN GROUPING(service) = 1 THEN 'ALL SERVICES'
              ELSE COALESCE(service, 'UNKNOWN SERVICE') END AS service,
    COUNT(*) AS source_shipments,
    SUM(CASE WHEN result_status IN ('ROUTE_OR_DETAIL_TIME_UNRESOLVED',
      'MISSING_ROUTE_FIELDS', 'OUTSIDE_SAME_LEG_SCOPE') THEN 1 ELSE 0 END)
      AS route_scope_excluded,
    SUM(CASE WHEN result_status = 'SHIPMENT_CREATION_UNRESOLVED' THEN 1 ELSE 0 END)
      AS creation_time_unresolved,
    SUM(CASE WHEN result_status IN ('NO_EXACT_STOP', 'AMBIGUOUS_STOP',
      'STOP_FLAGS_REQUIRE_REVIEW', 'CUTOFF_UNRESOLVED') THEN 1 ELSE 0 END)
      AS stop_or_cutoff_unresolved,
    SUM(CASE WHEN result_status IN ('CUTOFF_BEFORE_SELECTED_START',
      'INSUFFICIENT_FOLLOWUP') THEN 1 ELSE 0 END) AS cutoff_period_excluded,
    SUM(CASE WHEN result_status = 'OUTSIDE_DISPLAY_WINDOW' THEN 1 ELSE 0 END)
      AS outside_display_window,
    SUM(CASE WHEN result_status = 'IN_WINDOW' THEN 1 ELSE 0 END)
      AS records_in_window,
    SUM(CASE WHEN result_status = 'IN_WINDOW'
      AND record_created_at < cutoff_ts THEN 1 ELSE 0 END) AS before_cutoff,
    SUM(CASE WHEN result_status = 'IN_WINDOW'
      AND record_created_at = cutoff_ts THEN 1 ELSE 0 END) AS exactly_at_cutoff,
    SUM(CASE WHEN result_status = 'IN_WINDOW'
      AND record_created_at > cutoff_ts THEN 1 ELSE 0 END) AS after_cutoff
  FROM classified
  GROUP BY GROUPING SETS ((service), ())
),
counts AS (
  SELECT service, day_from_cutoff, COUNT(*) AS records_created
  FROM classified WHERE result_status = 'IN_WINDOW'
  GROUP BY service, day_from_cutoff
  UNION ALL
  SELECT 'ALL SERVICES', day_from_cutoff, COUNT(*)
  FROM classified WHERE result_status = 'IN_WINDOW'
  GROUP BY day_from_cutoff
),
day_grid AS (
  SELECT *, EXPLODE(SEQUENCE(-28, 13)) AS day_from_cutoff FROM coverage
),
filled AS (
  SELECT g.*, COALESCE(c.records_created, 0) AS records_created
  FROM day_grid g LEFT JOIN counts c
    ON c.service = g.service AND c.day_from_cutoff = g.day_from_cutoff
),
running AS (
  SELECT *, SUM(records_created) OVER (
    PARTITION BY service ORDER BY day_from_cutoff
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_records
  FROM filled
)
SELECT r.*, r.day_from_cutoff + 1 AS bucket_end_day,
  ROUND(100.0 * cumulative_records / NULLIF(records_in_window, 0), 2)
    AS cumulative_pct_of_window,
  ROUND(100.0 * records_in_window / NULLIF(source_shipments, 0), 2)
    AS included_pct_of_source,
  ROUND(100.0 * after_cutoff / NULLIF(records_in_window, 0), 2)
    AS after_pct_of_window,
  records_in_window > 0 AS has_usable_records,
  p.as_of_utc, p.first_detail_utc, p.first_cutoff_utc
FROM running r CROSS JOIN params p
ORDER BY service, day_from_cutoff;
```

## Dataset B — finalized allocation revisions

Paste this entire block into the second dataset SQL editor and run it once.

The quantity is `reviewed_teu - last_reviewed_teu` as stored in the change log. Only identifiable, non-deleted, finalized, TCC-accepted rows with two nonnegative numeric values enter the chart. Null previous values are not treated as zero. Increases and decreases are shown separately as positive magnitudes.

The date is taken from the recorded compact timestamp without assigning a timezone. These are recorded finalization dates, which can differ from the earlier edit or submission date. One business action may have several records; these are not counts of unique transfers. Repeated revisions can concern the same space, so adding them does not measure unique capacity moved.

```sql
-- Read-only allocation dataset. Counts and TEU describe recorded revisions.
-- Raw update dates are calendar dates; their timezone has not been established.
WITH params AS (
  SELECT DATE '2026-06-01' AS first_recorded_date,
         CURRENT_DATE() AS last_recorded_date
),
raw_distinct AS (
  SELECT DISTINCT
    id AS change_log_id, csal_id AS plan_id,
    NULLIF(UPPER(TRIM(service)), '') AS service,
    customer, agreement, tcr, week_num, vessel_voyage,
    TRIM(updated_on) AS raw_update_time,
    updated_by, deleted,
    LOWER(TRIM(status)) AS plan_status,
    LOWER(TRIM(acceptance_status)) AS approval_status,
    TRY_CAST(last_reviewed_teu AS DECIMAL(18,6)) AS previous_reviewed_teu,
    TRY_CAST(reviewed_teu AS DECIMAL(18,6)) AS current_reviewed_teu
  FROM datasources.csal.csal_change_log
),
identified AS (
  SELECT *, COUNT(*) OVER (PARTITION BY change_log_id) AS versions_of_id,
    CASE WHEN raw_update_time RLIKE '^[0-9]{14}([.][0-9]{1,9})?$'
      THEN TRY_CAST(CONCAT(SUBSTRING(raw_update_time, 1, 4), '-',
                           SUBSTRING(raw_update_time, 5, 2), '-',
                           SUBSTRING(raw_update_time, 7, 2)) AS DATE)
    END AS recorded_date
  FROM raw_distinct
),
scoped AS (
  SELECT i.*, p.first_recorded_date, p.last_recorded_date,
    current_reviewed_teu - previous_reviewed_teu AS recorded_teu_difference
  FROM identified i CROSS JOIN params p
  WHERE plan_status = 'finalized'
    AND (recorded_date BETWEEN p.first_recorded_date AND p.last_recorded_date
         OR recorded_date IS NULL)
),
classified AS (
  SELECT *, CASE
    WHEN recorded_date IS NULL THEN 'UNDATED_FINALIZED_ROW'
    WHEN change_log_id IS NULL OR plan_id IS NULL OR versions_of_id <> 1
      THEN 'ID_UNRESOLVED'
    WHEN deleted IS NULL OR deleted = TRUE
      OR approval_status IS NULL OR approval_status <> 'tcc accepted'
      THEN 'DELETION_OR_APPROVAL_UNRESOLVED'
    WHEN previous_reviewed_teu IS NULL OR current_reviewed_teu IS NULL
      THEN 'PREVIOUS_OR_CURRENT_VALUE_MISSING'
    WHEN previous_reviewed_teu < 0 OR current_reviewed_teu < 0
      THEN 'NEGATIVE_ALLOCATION_REQUIRES_REVIEW'
    WHEN recorded_teu_difference > 0 THEN 'INCREASE'
    WHEN recorded_teu_difference < 0 THEN 'DECREASE'
    ELSE 'UNCHANGED'
  END AS revision_kind
  FROM scoped
),
coverage AS (
  SELECT CASE WHEN GROUPING(service) = 1 THEN 'ALL SERVICES'
              ELSE COALESCE(service, 'UNKNOWN SERVICE') END AS service,
    SUM(CASE WHEN recorded_date IS NOT NULL THEN 1 ELSE 0 END)
      AS dated_finalized_rows,
    SUM(CASE WHEN recorded_date IS NULL THEN 1 ELSE 0 END)
      AS undated_finalized_rows_all_history,
    SUM(CASE WHEN revision_kind IN ('INCREASE', 'DECREASE', 'UNCHANGED')
      THEN 1 ELSE 0 END) AS comparable_revision_rows,
    SUM(CASE WHEN revision_kind = 'PREVIOUS_OR_CURRENT_VALUE_MISSING'
      THEN 1 ELSE 0 END) AS missing_value_rows,
    SUM(CASE WHEN revision_kind IN ('ID_UNRESOLVED',
      'DELETION_OR_APPROVAL_UNRESOLVED', 'NEGATIVE_ALLOCATION_REQUIRES_REVIEW')
      THEN 1 ELSE 0 END) AS other_excluded_rows,
    SUM(CASE WHEN revision_kind = 'INCREASE' THEN 1 ELSE 0 END) AS increase_rows,
    SUM(CASE WHEN revision_kind = 'DECREASE' THEN 1 ELSE 0 END) AS decrease_rows,
    SUM(CASE WHEN revision_kind = 'UNCHANGED' THEN 1 ELSE 0 END) AS unchanged_rows,
    COUNT(DISTINCT CASE WHEN revision_kind IN ('INCREASE', 'DECREASE')
      THEN plan_id END) AS plans_with_recorded_changes
  FROM classified
  GROUP BY GROUPING SETS ((service), ())
),
counts AS (
  SELECT COALESCE(service, 'UNKNOWN SERVICE') AS service, recorded_date,
    SUM(CASE WHEN revision_kind = 'INCREASE'
      THEN recorded_teu_difference ELSE 0 END) AS increased_teu,
    SUM(CASE WHEN revision_kind = 'DECREASE'
      THEN -recorded_teu_difference ELSE 0 END) AS decreased_teu,
    SUM(CASE WHEN revision_kind = 'INCREASE' THEN 1 ELSE 0 END)
      AS daily_increase_rows,
    SUM(CASE WHEN revision_kind = 'DECREASE' THEN 1 ELSE 0 END)
      AS daily_decrease_rows
  FROM classified
  WHERE revision_kind IN ('INCREASE', 'DECREASE', 'UNCHANGED')
  GROUP BY service, recorded_date
  UNION ALL
  SELECT 'ALL SERVICES', recorded_date,
    SUM(CASE WHEN revision_kind = 'INCREASE'
      THEN recorded_teu_difference ELSE 0 END),
    SUM(CASE WHEN revision_kind = 'DECREASE'
      THEN -recorded_teu_difference ELSE 0 END),
    SUM(CASE WHEN revision_kind = 'INCREASE' THEN 1 ELSE 0 END),
    SUM(CASE WHEN revision_kind = 'DECREASE' THEN 1 ELSE 0 END)
  FROM classified
  WHERE revision_kind IN ('INCREASE', 'DECREASE', 'UNCHANGED')
  GROUP BY recorded_date
),
date_grid AS (
  SELECT c.*, EXPLODE(SEQUENCE(p.first_recorded_date, p.last_recorded_date,
                              INTERVAL 1 DAY)) AS recorded_date
  FROM coverage c CROSS JOIN params p
)
SELECT g.*,
  CASE DATE_FORMAT(g.recorded_date, 'EEE')
    WHEN 'Mon' THEN '1 Mon' WHEN 'Tue' THEN '2 Tue'
    WHEN 'Wed' THEN '3 Wed' WHEN 'Thu' THEN '4 Thu'
    WHEN 'Fri' THEN '5 Fri' WHEN 'Sat' THEN '6 Sat'
    WHEN 'Sun' THEN '7 Sun' END AS weekday_label,
  COALESCE(c.increased_teu, 0) AS increased_teu,
  COALESCE(c.decreased_teu, 0) AS decreased_teu,
  COALESCE(c.daily_increase_rows, 0) AS daily_increase_rows,
  COALESCE(c.daily_decrease_rows, 0) AS daily_decrease_rows,
  ROUND(100.0 * g.comparable_revision_rows / NULLIF(g.dated_finalized_rows, 0), 2)
    AS comparable_rows_pct,
  g.comparable_revision_rows > 0 AS has_comparable_records,
  p.first_recorded_date, p.last_recorded_date
FROM date_grid g CROSS JOIN params p
LEFT JOIN counts c ON c.service = g.service AND c.recorded_date = g.recorded_date
ORDER BY g.service, g.recorded_date;
```

## 1. Set up the service selector first

Both datasets contain individual services **and a separately calculated `ALL SERVICES` total**. Selecting the UI's generic **All** would include both and double-count shipment and TEU totals.

1. Return to the dashboard canvas and add a **Single value** filter. Name it **Service**.
2. Under **Fields**, add `service` from the shipment dataset and `service` from `allocation_revisions` to this same filter.
3. Turn **Allow All** off. Set the selected/default value to the literal **`ALL SERVICES`** returned by the queries.
4. Remove the old chart-level `service` filter if it pins a different service. Let the shared selector control both datasets.
5. Check that choosing one named service changes both analyses. Some services may have no qualifying allocation revisions; a blank chart means no qualifying data, not proof of no activity.

If one filter cannot be connected to both datasets in your editor, use one Single value selector per dataset with the same instructions. Keep both selections identical when comparing them. Do not select multiple services together for these percentage curves.

A single-value filter can target fields in multiple datasets; its generic All option is controlled separately. [Databricks filter controls](https://docs.databricks.com/aws/en/dashboards/manage/filter-types)

## 2. Chart 1 — daily shipment timing

Use the existing daily line chart if it is already present.

| Setting | Value |
|---|---|
| Dataset | Shipment dataset / `shipment_timing` |
| Visualization | Line |
| X axis | `day_from_cutoff` |
| X transform | **None** |
| X scale / order | Continuous, ascending |
| Y axis | `records_created` |
| Y transform | **SUM** |
| Y minimum | 0 |
| Color | One series; do not add `service` as a second grouping |
| Widget filter | `has_usable_records` = true |
| Title | **Shipment records by day relative to TCR cutoff** |
| X display name | **Days from TCR cutoff** |
| Y display name | **Shipment records** |

Turn on **Title** and **Description** in the Widget panel. Paste this description:

> Day 0 starts at the TCR cutoff. Negative days are before it; positive days are after it. Counts use uniquely matched, same-leg shipment records. Record creation is not yet confirmed as original customer booking time.

Under **Annotation**, add a **vertical constant line at 0**, labeled **TCR cutoff**. Use a straight line shape, not smoothing. Keep hover tooltips on so a day shows the exact count.

**How to read it:** a point at -10 counts records created from 10 days before cutoff up to, but not including, 9 days before cutoff. Day 0 covers the first 24 hours starting at cutoff; it is not the whole calendar date. A high point shows concentrated activity, not a proven best recommendation date.

## 3. Chart 2 — cumulative share recorded by each day

Add another visualization below Chart 1 and use the same shipment dataset.

| Setting | Value |
|---|---|
| Visualization | Line |
| X axis | **`bucket_end_day`** |
| X transform / scale | None / Continuous, ascending |
| Y axis | `cumulative_pct_of_window` |
| Y transform | **MAX** |
| Y limits | Minimum 0, maximum 100 |
| Number format | Ordinary number, 1 decimal; values are already 0–100 |
| Widget filter | `has_usable_records` = true |
| Title | **Cumulative share of shipment records around TCR cutoff** |
| X display name | **Days from TCR cutoff** |
| Y display name | **Share of records in the window (%)** |
| Annotation | Vertical constant at 0, labeled TCR cutoff |

Description:

> Share of matched shipment records accumulated within the -28 to +14 day window. At day 0, the curve shows the share recorded before cutoff. The denominator is this observation window, not all eventual bookings or final TEU.

**Use `bucket_end_day`, not `day_from_cutoff`, for this chart.** Daily counts are labeled by the start of a 24-hour bucket; cumulative totals describe its end. This avoids displaying a full day's post-cutoff records at day 0. The cumulative point at 0 excludes records created exactly at cutoff; those enter the next bucket.

**Checks:** the curve never falls, and it ends at 100% at +14 when the selected service has usable records. It starts at -27 after accumulating the first bucket; records earlier than -28 are outside the denominator. Do not average or add percentage curves from different services.

This curve describes the arrival of records. It does not establish when donor/receiver classifications become reliable; that needs allocation and outcome definitions at a consistent case level.

## 4. Chart 3 — allocation revisions by weekday

Add a Bar visualization below the two timing curves and select `allocation_revisions`.

| Setting | Value |
|---|---|
| X axis | `weekday_label` |
| X transform / scale | None / Categorical, ascending |
| Bar arrangement | Grouped, not stacked |
| Y field 1 | `increased_teu`, transform SUM |
| Y field 2 | `decreased_teu`, transform SUM |
| Y minimum | 0 |
| Widget filter | `has_comparable_records` = true |
| Title | **Allocation revisions by recorded weekday** |
| X display name | **Recorded finalization weekday** |
| Y display name | **Recorded TEU differences** |
| Legend names | Increase / Decrease |

Description:

> Differences between stored reviewed and previous reviewed allocations, totaled by recorded weekday. Both series show positive magnitudes. These are finalized allocation revisions, not confirmed swaps. Recorded dates have an unconfirmed timezone and have not been aligned to TCR cutoff.

Use two clearly different colors and keep the legend visible. A dark blue and red work on a light background; on a dark background use a lighter blue so both bar series remain visible. Exact styling is optional.

If the editor supports only one Y field initially, use **+** beside Y axis to add the second. Do not put one series on a differently scaled secondary axis. Tooltips can include `daily_increase_rows` and `daily_decrease_rows` with SUM.

**How to read it:** taller bars show weekdays with more recorded TEU increases or decreases. Labels run from 1 Mon through 7 Sun to preserve weekday order. Similar increases and decreases do not establish a transfer between two customers. Totals are not adjusted for how many of each weekday fall in the selected period. This chart describes the weekly pattern; it does not establish which calendar or deadline caused it.

**Do not add a TCR cutoff line to this weekday chart.** Cutoffs can fall on different days for different voyages and ports.

### If you need actual dates instead

Use this same widget and dataset. Change the visualization to **Line**, set X to `recorded_date` with **None**, day granularity, ascending order; keep SUM of `increased_teu` and SUM of `decreased_teu` on the same Y axis. Use a straight line shape. Title it **Recorded allocation revisions by date**. Update the description to say that the axis shows recorded finalization dates.

This is an alternative view of the same records. It helps investigate a particular spike; keep just the view needed for the discussion. Neither version compares revisions with TCR cutoff.

## 5. Compact table — shipment coverage

Add a **Table** using the shipment dataset. These figures repeat on every day row; use **MAX**, never SUM, for each numeric field. Show `service` as the single grouping column.

| Field | Display name | Transform |
|---|---|---|
| `service` | Service | None |
| `source_shipments` | Source shipments in scope | MAX |
| `records_in_window` | Included in timing curves | MAX |
| `included_pct_of_source` | Included (%) | MAX |
| `route_scope_excluded` | Route or detail-time exclusions | MAX |
| `creation_time_unresolved` | Shipment time unresolved | MAX |
| `stop_or_cutoff_unresolved` | Stop / cutoff unresolved | MAX |
| `cutoff_period_excluded` | Cutoff period excluded | MAX |
| `outside_display_window` | Outside timing window | MAX |

Title: **Shipment coverage and exclusions**.

Description:

> Counts refer to latest booking-detail records in the selected creation period, plus rows with missing detail creation dates. Exclusion reasons are assigned in sequence, once per shipment. They are not independent error rates.

Keep this table unfiltered by `has_usable_records`; it must remain visible when timing data is unavailable. If the columns are too wide, shorten the display labels or allow horizontal scrolling. Do not hide the coverage denominator.

Reconciliation:

`Source shipments = Included + Route/detail exclusions + Shipment time unresolved + Stop/cutoff unresolved + Cutoff period excluded + Outside timing window`.

The **included percentage is not a pure match rate**: deliberate route and date restrictions also reduce it. A source total of zero should lead to an empty timing chart and a null percentage, not a claim of 0% late bookings.

For an optional before/after detail table, use MAX of `before_cutoff`, `exactly_at_cutoff`, `after_cutoff`, and `after_pct_of_window` from Dataset A. These counts use exact timestamp ordering; they are not extra source queries. They reconcile to `records_in_window`.

## 6. Compact table — allocation coverage

Add a **Table** using `allocation_revisions`. Use `service` with None and **MAX** for every numeric field.

| Field | Display name |
|---|---|
| `dated_finalized_rows` | Dated finalized records |
| `comparable_revision_rows` | Records with comparable values |
| `comparable_rows_pct` | Comparable (%) |
| `missing_value_rows` | Previous/current value missing |
| `other_excluded_rows` | ID / approval / value exclusions |
| `increase_rows` | Increase records |
| `decrease_rows` | Decrease records |
| `unchanged_rows` | Unchanged records |
| `undated_finalized_rows_all_history` | Undated records; all available history |

Title: **Allocation revision coverage**.

Description:

> Comparable records have two recorded allocation values and pass the ID, approval and deletion checks. Undated records cannot be assigned to the selected period and are reported separately across available history.

Keep this table unfiltered by `has_comparable_records`. Do not call `increase_rows + decrease_rows` the number of swaps. Do not call the proportion of plans with a change the share of all plans unless a complete first-finalization denominator is established.

Reconciliation:

- `Dated finalized records = Comparable records + Missing value records + Other exclusions`.
- `Comparable records = Increase records + Decrease records + Unchanged records`.

## 7. Finish the page

Use one plain page called **Timing and allocation changes**. Place the Service selector at the top, the daily and cumulative curves underneath, then the allocation weekday chart, and the two compact coverage tables at the bottom. Resize the charts so axis labels, titles, and tooltips are readable. There is no need for decorative KPI tiles, pie charts, or repeated charts of the same metric.

Add a short text widget above the charts:

> This dashboard compares shipment-record timing with the latest available TCR cutoff and shows recorded allocation revisions. It supports investigation of when sales recommendations could be useful. Original booking-time meaning, historical allocation-to-cutoff mapping, and swap confirmation remain unresolved.

A vertical reference line, axis aggregation and chart titles are configured in the visualization editor. [Databricks chart settings](https://docs.databricks.com/aws/en/dashboards/manage/visualizations)

## 8. Final checks before presenting

1. **One service selection:** select the literal `ALL SERVICES`, then a named service. The coverage tables should show one service row. Do not use generic All or select synthetic totals together with individual services.
2. **Daily total:** sum the shipment dataset's `records_created` for the selected service. It must equal its `records_in_window`. Repeated totals use MAX in tables.
3. **Curve shape:** daily X uses None and Y uses SUM. If the plot collapses into one point, X is being aggregated. If it becomes vertical spikes, check that Y has SUM and one service scope is selected.
4. **Cumulative endpoint:** for a non-empty service, it rises to 100 at +14. Its X is `bucket_end_day`; the daily chart's X is `day_from_cutoff`.
5. **Coverage:** both reconciliation equations above must balance. Zero/no usable records must not be presented as zero after-cutoff activity or zero allocation changes.
6. **Dates:** confirm the source refresh is sufficiently current for the stated follow-up period. Read the returned `as_of_utc` in Dataset A; do not describe the reporting date as a recovered historical snapshot.
7. **Descriptions:** retain the timestamp and allocation interpretation notes. Source definitions cannot be confirmed from chart appearance.
8. Publish the checked draft using the intended existing access settings.

These queries were parsed as Databricks SQL and their translated logic was tested locally with synthetic records. Checks cover duplicate/ambiguous records, missing values, empty data, all-service totals and cutoff-window boundaries. They were not run in Databricks during preparation of this guide. That does not substitute for execution against your Databricks sources. No new live Databricks execution or dashboard publication is claimed by this guide.

## What is still needed for the original business conclusion

The charts above finish the supported descriptive dashboard. The original question—**when should we recommend a swap?**—is not fully answered yet.

| Missing evidence | What it enables |
|---|---|
| Definition of original booking time, or an authoritative source field | Calling the shipment curve a customer booking curve. |
| Approved definition of a CSAL case and its historically applicable allocation | Measuring whether demand versus allocation becomes informative before cutoff. |
| A historical route/port-call/cutoff link for each relevant allocation event | Putting allocation changes on a days-to-TCR axis. Both sides may have different cutoffs. |
| Confirmed audit timestamp timezone and event stage | Correctly ordering edit, submission or finalization against UTC cutoff. |
| A transfer reference or business-reviewed source/destination/quantity evidence | Distinguishing swaps from cancellations, corrections, demerit adjustments and unrelated edits. |

Once the event-to-cutoff mapping and timezone are confirmed, build the allocation curve using days from the applicable cutoff, retaining separate increases and decreases. Do not borrow the other plan's cutoff, assign a plan's earliest/latest cutoff, or assume TCR/office codes are loading ports. Compare that curve with the shipment timing curve before proposing a recommendation window.

No extra plotting cell can supply these missing facts. Keep any proposed recommendation day labeled as a hypothesis until the two timelines are comparable and its usefulness has been checked with the business. The files and instructions can be complete while that business validation remains outstanding.
