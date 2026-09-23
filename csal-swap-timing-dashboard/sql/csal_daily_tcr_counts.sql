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
    SUM(CASE WHEN rec_cre_dt_utc IS NULL THEN 1 ELSE 0 END) AS missing_creation_rows
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
    d.detail_record_created_at,
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
    d.detail_record_created_at,
    sh.record_created_at, sh.distinct_creation_times, sh.missing_creation_rows
),
eligible AS (
  SELECT m.service, m.shipment_num,
    CAST(FLOOR((CAST(m.record_created_at AS LONG) - CAST(m.cutoff_ts AS LONG))
               / 86400.0) AS INT) AS day_from_cutoff
  FROM matched m
  CROSS JOIN params p
  WHERE m.current_route_variants = 1
    AND m.corp_svvd IS NOT NULL AND m.first_svvd = m.corp_svvd
    AND m.loading_port IS NOT NULL AND m.first_port = m.loading_port
    AND m.distinct_creation_times = 1 AND m.missing_creation_rows = 0
    AND m.exact_stops = 1 AND m.exact_stop_rows = 1
    AND m.max_stop_revision_rows = 1 AND m.distinct_cutoffs = 1
    AND m.flagged_stop = 0
    AND m.detail_record_created_at >= p.first_detail_utc
    AND m.detail_record_created_at <= p.as_of_utc
    AND m.cutoff_ts >= p.first_cutoff_utc
    AND m.cutoff_ts <= p.as_of_utc - INTERVAL 14 DAYS
),
windowed AS (
  SELECT * FROM eligible WHERE day_from_cutoff BETWEEN -28 AND 13
),
counts AS (
  SELECT service, day_from_cutoff, COUNT(*) AS records_created
  FROM windowed GROUP BY service, day_from_cutoff
  UNION ALL
  SELECT 'ALL SERVICES', day_from_cutoff, COUNT(*)
  FROM windowed GROUP BY day_from_cutoff
),
service_totals AS (
  SELECT service, SUM(records_created) AS records_in_window
  FROM counts GROUP BY service
),
day_grid AS (
  SELECT service, records_in_window, EXPLODE(SEQUENCE(-28, 13)) AS day_from_cutoff
  FROM service_totals
),
filled AS (
  SELECT g.service, g.day_from_cutoff, g.records_in_window,
    COALESCE(c.records_created, 0) AS records_created
  FROM day_grid g
  LEFT JOIN counts c ON c.service = g.service
                    AND c.day_from_cutoff = g.day_from_cutoff
)
SELECT service, day_from_cutoff, records_created, records_in_window,
  SUM(records_created) OVER (
    PARTITION BY service ORDER BY day_from_cutoff
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_records,
  ROUND(100.0 * SUM(records_created) OVER (
    PARTITION BY service ORDER BY day_from_cutoff
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) / records_in_window, 1) AS cumulative_pct_of_window
FROM filled
ORDER BY service, day_from_cutoff;
