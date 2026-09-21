WITH nrt_prepared AS (
  SELECT
    NULLIF(TRIM(CAST(booking_number AS STRING)), '') AS booking_number,
    NULLIF(TRIM(CAST(customer AS STRING)), '') AS customer,
    NULLIF(TRIM(CAST(service AS STRING)), '') AS service,
    NULLIF(UPPER(TRIM(CAST(svvd AS STRING))), '') AS svvd,
    NULLIF(UPPER(TRIM(CAST(tcr AS STRING))), '') AS tcr,
    NULLIF(TRIM(CAST(week_num AS STRING)), '') AS week_num,
    NULLIF(TRIM(CAST(booking_status AS STRING)), '') AS booking_status,
    CAST(tcr_cutoff AS STRING) AS tcr_cutoff_raw,
    TRY_CAST(tcr_cutoff AS TIMESTAMP) AS tcr_cutoff,
    TRY_CAST(run_date AS TIMESTAMP) AS selected_nrt_run_ts
  FROM dev.crmi_gold.csal_teu_performance_nrt
),
nrt_ranked AS (
  SELECT
    *,
    COUNT(*) OVER (
      PARTITION BY booking_number, svvd, tcr
    ) AS nrt_snapshot_row_count,
    ROW_NUMBER() OVER (
      PARTITION BY booking_number, svvd, tcr
      ORDER BY
        selected_nrt_run_ts DESC NULLS LAST,
        tcr_cutoff DESC NULLS LAST,
        SHA2(
          CONCAT_WS(
            '||',
            COALESCE(customer, '<NULL>'),
            COALESCE(service, '<NULL>'),
            COALESCE(week_num, '<NULL>'),
            COALESCE(booking_status, '<NULL>')
          ),
          256
        ) DESC
    ) AS snapshot_rank
  FROM nrt_prepared
  WHERE booking_number IS NOT NULL
),
nrt_latest AS (
  SELECT *
  FROM nrt_ranked
  WHERE snapshot_rank = 1
),
shipment_prepared AS (
  SELECT
    NULLIF(TRIM(CAST(shipment_number AS STRING)), '') AS booking_number,
    NULLIF(UPPER(TRIM(CAST(tcr AS STRING))), '') AS tcr,
    COALESCE(
      TRY_CAST(rec_cre_dt_utc AS TIMESTAMP),
      TRY_TO_TIMESTAMP(CAST(rec_cre_dt_utc AS STRING), 'yyyyMMddHHmmss.SSS'),
      TRY_TO_TIMESTAMP(CAST(rec_cre_dt_utc AS STRING), 'yyyyMMddHHmmss')
    ) AS record_created_at
  FROM datasources.csal.csal_shipment
),
shipment_exact AS (
  SELECT
    booking_number,
    tcr,
    MIN(record_created_at) AS record_created_at,
    COUNT(*) AS shipment_source_row_count
  FROM shipment_prepared
  WHERE booking_number IS NOT NULL
  GROUP BY booking_number, tcr
),
shipment_booking_profile AS (
  SELECT
    booking_number,
    COUNT(*) AS shipment_booking_row_count,
    COUNT(DISTINCT tcr) AS shipment_distinct_tcr_count
  FROM shipment_prepared
  WHERE booking_number IS NOT NULL
  GROUP BY booking_number
),
joined AS (
  SELECT
    SHA2(
      CONCAT_WS(
        '||',
        COALESCE(UPPER(n.booking_number), '<NULL>'),
        COALESCE(n.svvd, '<NULL>'),
        COALESCE(n.tcr, '<NULL>')
      ),
      256
    ) AS booking_tcr_key,
    n.booking_number,
    n.customer,
    n.service,
    n.svvd,
    n.tcr,
    n.week_num,
    n.booking_status,
    n.tcr_cutoff_raw,
    n.tcr_cutoff,
    n.selected_nrt_run_ts,
    n.nrt_snapshot_row_count,
    s.record_created_at,
    s.shipment_source_row_count,
    p.shipment_booking_row_count,
    p.shipment_distinct_tcr_count,
    CASE
      WHEN s.booking_number IS NOT NULL
           AND s.record_created_at IS NOT NULL
        THEN 'EXACT_BOOKING_TCR_MATCH'
      WHEN s.booking_number IS NOT NULL
        THEN 'EXACT_MATCH_MISSING_CREATION_TS'
      WHEN p.booking_number IS NOT NULL
        THEN 'BOOKING_MATCH_TCR_MISMATCH_OR_NULL'
      ELSE 'NO_SHIPMENT_BOOKING_MATCH'
    END AS join_status,
    (
      s.booking_number IS NOT NULL
      AND s.record_created_at IS NOT NULL
      AND n.tcr_cutoff IS NOT NULL
    ) AS is_valid_timing_record
  FROM nrt_latest n
  LEFT JOIN shipment_exact s
    ON s.booking_number = n.booking_number
   AND n.tcr IS NOT NULL
   AND s.tcr = n.tcr
  LEFT JOIN shipment_booking_profile p
    ON p.booking_number = n.booking_number
),
timed AS (
  SELECT
    *,
    CASE
      WHEN is_valid_timing_record THEN
        ROUND(
          (
            CAST(UNIX_TIMESTAMP(tcr_cutoff) AS DOUBLE)
            - CAST(UNIX_TIMESTAMP(record_created_at) AS DOUBLE)
          ) / 3600.0,
          2
        )
    END AS hours_before_tcr,
    CASE
      WHEN is_valid_timing_record THEN
        ROUND(
          (
            CAST(UNIX_TIMESTAMP(tcr_cutoff) AS DOUBLE)
            - CAST(UNIX_TIMESTAMP(record_created_at) AS DOUBLE)
          ) / 86400.0,
          3
        )
    END AS days_before_tcr,
    CASE
      WHEN is_valid_timing_record THEN
        DATEDIFF(TO_DATE(tcr_cutoff), TO_DATE(record_created_at))
    END AS calendar_days_before_tcr
  FROM joined
)
SELECT
  *,
  CASE
    WHEN NOT is_valid_timing_record THEN 'Not scorable'
    WHEN hours_before_tcr < 0 THEN 'After cutoff'
    WHEN hours_before_tcr < 24 THEN 'Same day'
    WHEN hours_before_tcr < 96 THEN '1-3 days'
    WHEN hours_before_tcr < 192 THEN '4-7 days'
    WHEN hours_before_tcr < 360 THEN '8-14 days'
    WHEN hours_before_tcr < 744 THEN '15-30 days'
    ELSE '31+ days'
  END AS lead_time_bucket,
  CASE
    WHEN NOT is_valid_timing_record THEN 99
    WHEN hours_before_tcr < 0 THEN 0
    WHEN hours_before_tcr < 24 THEN 1
    WHEN hours_before_tcr < 96 THEN 2
    WHEN hours_before_tcr < 192 THEN 3
    WHEN hours_before_tcr < 360 THEN 4
    WHEN hours_before_tcr < 744 THEN 5
    ELSE 6
  END AS lead_time_bucket_sort,
  CASE
    WHEN is_valid_timing_record THEN hours_before_tcr < 0
  END AS is_after_cutoff,
  CASE
    WHEN tcr_cutoff IS NULL THEN 'MISSING_OR_UNPARSEABLE'
    WHEN tcr_cutoff_raw RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
      THEN 'DATE_ONLY'
    WHEN DATE_FORMAT(tcr_cutoff, 'HH:mm:ss') = '00:00:00'
      THEN 'MIDNIGHT_TIME_UNCONFIRMED'
    ELSE 'TIMESTAMP'
  END AS cutoff_precision_flag,
  TRUE AS creation_timestamp_is_proxy,
  'csal_shipment.rec_cre_dt_utc' AS creation_timestamp_source
FROM timed;
