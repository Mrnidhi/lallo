WITH nrt_normalized AS (
  SELECT DISTINCT
    NULLIF(UPPER(TRIM(CAST(booking_number AS STRING))), '') AS booking_number,
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
nrt_keyed AS (
  SELECT
    *,
    CASE
      WHEN booking_number IS NOT NULL THEN CONCAT_WS(
        '||',
        'BOOKING',
        booking_number,
        COALESCE(svvd, '<NULL>'),
        COALESCE(tcr, '<NULL>')
      )
      ELSE CONCAT_WS(
        '||',
        'MISSING_BOOKING',
        SHA2(
          CONCAT_WS(
            '||',
            COALESCE(customer, '<NULL>'),
            COALESCE(service, '<NULL>'),
            COALESCE(svvd, '<NULL>'),
            COALESCE(tcr, '<NULL>'),
            COALESCE(week_num, '<NULL>'),
            COALESCE(booking_status, '<NULL>'),
            COALESCE(tcr_cutoff_raw, '<NULL>')
          ),
          256
        )
      )
    END AS nrt_entity_key
  FROM nrt_normalized
),
nrt_profiled AS (
  SELECT
    *,
    COUNT(*) OVER (
      PARTITION BY nrt_entity_key
    ) AS nrt_snapshot_row_count,
    MAX(
      COALESCE(
        selected_nrt_run_ts,
        CAST('1900-01-01 00:00:00' AS TIMESTAMP)
      )
    ) OVER (
      PARTITION BY nrt_entity_key
    ) AS latest_nrt_run_sort_ts
  FROM nrt_keyed
),
nrt_latest_run_rows AS (
  SELECT *
  FROM nrt_profiled
  WHERE COALESCE(
          selected_nrt_run_ts,
          CAST('1900-01-01 00:00:00' AS TIMESTAMP)
        ) = latest_nrt_run_sort_ts
),
nrt_ranked AS (
  SELECT
    *,
    COUNT(*) OVER (
      PARTITION BY nrt_entity_key
    ) AS latest_snapshot_row_count,
    ROW_NUMBER() OVER (
      PARTITION BY nrt_entity_key
      ORDER BY SHA2(
        CONCAT_WS(
          '||',
          COALESCE(customer, '<NULL>'),
          COALESCE(service, '<NULL>'),
          COALESCE(week_num, '<NULL>'),
          COALESCE(booking_status, '<NULL>'),
          COALESCE(tcr_cutoff_raw, '<NULL>')
        ),
        256
      )
    ) AS latest_snapshot_rank
  FROM nrt_latest_run_rows
),
nrt_latest AS (
  SELECT
    SHA2(nrt_entity_key, 256) AS booking_tcr_key,
    booking_number,
    customer,
    service,
    svvd,
    tcr,
    week_num,
    booking_status,
    tcr_cutoff_raw,
    tcr_cutoff,
    selected_nrt_run_ts,
    nrt_snapshot_row_count,
    latest_snapshot_row_count,
    latest_snapshot_row_count > 1 AS has_ambiguous_latest_snapshot
  FROM nrt_ranked
  WHERE latest_snapshot_rank = 1
),
shipment_normalized AS (
  SELECT DISTINCT
    NULLIF(UPPER(TRIM(CAST(shipment_number AS STRING))), '') AS booking_number,
    NULLIF(UPPER(TRIM(CAST(tcr AS STRING))), '') AS shipment_tcr,
    NULLIF(UPPER(TRIM(CAST(sub_tcr AS STRING))), '') AS shipment_sub_tcr,
    NULLIF(UPPER(TRIM(CAST(sub_tcr_group AS STRING))), '') AS shipment_sub_tcr_group,
    COALESCE(
      TRY_CAST(rec_cre_dt_utc AS TIMESTAMP),
      TRY_TO_TIMESTAMP(CAST(rec_cre_dt_utc AS STRING), 'yyyyMMddHHmmss.SSS'),
      TRY_TO_TIMESTAMP(CAST(rec_cre_dt_utc AS STRING), 'yyyyMMddHHmmss')
    ) AS record_created_at
  FROM datasources.csal.csal_shipment
  WHERE NULLIF(TRIM(CAST(shipment_number AS STRING)), '') IS NOT NULL
),
shipment_candidate_tcrs AS (
  SELECT
    booking_number,
    shipment_tcr AS candidate_tcr,
    record_created_at,
    'TCR' AS candidate_source
  FROM shipment_normalized
  WHERE shipment_tcr IS NOT NULL

  UNION ALL

  SELECT
    booking_number,
    shipment_sub_tcr AS candidate_tcr,
    record_created_at,
    'SUB_TCR' AS candidate_source
  FROM shipment_normalized
  WHERE shipment_sub_tcr IS NOT NULL

  UNION ALL

  SELECT
    booking_number,
    shipment_sub_tcr_group AS candidate_tcr,
    record_created_at,
    'SUB_TCR_GROUP' AS candidate_source
  FROM shipment_normalized
  WHERE shipment_sub_tcr_group IS NOT NULL
),
shipment_by_booking_tcr AS (
  SELECT
    booking_number,
    candidate_tcr,
    MIN(record_created_at) AS record_created_at,
    COUNT(*) AS shipment_candidate_row_count,
    COUNT(DISTINCT record_created_at) AS candidate_creation_ts_count,
    SUM(CASE WHEN record_created_at IS NULL THEN 1 ELSE 0 END)
      AS candidate_null_creation_ts_row_count,
    CONCAT_WS(',', SORT_ARRAY(COLLECT_SET(candidate_source))) AS candidate_sources
  FROM shipment_candidate_tcrs
  GROUP BY booking_number, candidate_tcr
),
shipment_booking_profile AS (
  SELECT
    booking_number,
    COUNT(*) AS shipment_normalized_row_count,
    COUNT(DISTINCT record_created_at) AS shipment_distinct_creation_ts_count,
    SUM(CASE WHEN record_created_at IS NULL THEN 1 ELSE 0 END)
      AS shipment_null_creation_ts_row_count,
    MIN(record_created_at) AS booking_record_created_at
  FROM shipment_normalized
  GROUP BY booking_number
),
shipment_tcr_profile AS (
  SELECT
    booking_number,
    COUNT(DISTINCT candidate_tcr) AS shipment_distinct_tcr_count
  FROM shipment_candidate_tcrs
  GROUP BY booking_number
),
exact_match AS (
  SELECT
    n.booking_tcr_key,
    s.record_created_at,
    s.candidate_tcr AS matched_shipment_tcr,
    s.candidate_sources,
    s.shipment_candidate_row_count,
    s.candidate_creation_ts_count,
    s.candidate_null_creation_ts_row_count
  FROM nrt_latest n
  INNER JOIN shipment_by_booking_tcr s
    ON s.booking_number = n.booking_number
   AND n.tcr IS NOT NULL
   AND s.candidate_tcr = n.tcr
),
resolved AS (
  SELECT
    n.booking_tcr_key,
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
    n.latest_snapshot_row_count,
    n.has_ambiguous_latest_snapshot,
    CASE
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count = 1
       AND e.candidate_null_creation_ts_row_count = 0
        THEN e.record_created_at
      WHEN e.booking_tcr_key IS NULL
       AND b.shipment_distinct_creation_ts_count = 1
       AND b.shipment_null_creation_ts_row_count = 0
        THEN b.booking_record_created_at
      ELSE NULL
    END AS record_created_at,
    e.matched_shipment_tcr,
    e.candidate_sources AS matched_tcr_sources,
    e.shipment_candidate_row_count AS matched_tcr_candidate_row_count,
    e.candidate_creation_ts_count AS matched_tcr_creation_ts_count,
    e.candidate_null_creation_ts_row_count
      AS matched_tcr_null_creation_ts_row_count,
    b.shipment_normalized_row_count,
    b.shipment_distinct_creation_ts_count,
    b.shipment_null_creation_ts_row_count,
    COALESCE(t.shipment_distinct_tcr_count, 0) AS shipment_distinct_tcr_count,
    CASE
      WHEN e.booking_tcr_key IS NOT NULL THEN 1
      WHEN e.booking_tcr_key IS NULL
       AND b.booking_number IS NOT NULL
       AND b.shipment_distinct_creation_ts_count = 1
       AND b.shipment_null_creation_ts_row_count = 0 THEN 2
      ELSE NULL
    END AS match_tier,
    CASE
      WHEN e.booking_tcr_key IS NOT NULL THEN 'EXACT_BOOKING_CANONICAL_TCR'
      WHEN e.booking_tcr_key IS NULL
       AND b.booking_number IS NOT NULL
       AND b.shipment_distinct_creation_ts_count = 1
       AND b.shipment_null_creation_ts_row_count = 0
        THEN 'UNIQUE_BOOKING_CREATION_TS_FALLBACK'
      ELSE 'NO_CONTROLLED_MATCH'
    END AS match_method,
    CASE
      WHEN n.booking_number IS NULL THEN 'NRT_BOOKING_NUMBER_MISSING'
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count = 1
       AND e.candidate_null_creation_ts_row_count = 0
        THEN 'EXACT_BOOKING_TCR_MATCH'
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count > 1
        THEN 'EXACT_MATCH_AMBIGUOUS_CREATION_TS'
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count = 1
       AND e.candidate_null_creation_ts_row_count > 0
        THEN 'EXACT_MATCH_MIXED_MISSING_CREATION_TS'
      WHEN e.booking_tcr_key IS NOT NULL
        THEN 'EXACT_MATCH_MISSING_CREATION_TS'
      WHEN b.booking_number IS NOT NULL
       AND b.shipment_distinct_creation_ts_count = 1
       AND b.shipment_null_creation_ts_row_count = 0
        THEN 'UNIQUE_BOOKING_NUMBER_MATCH'
      WHEN b.booking_number IS NOT NULL
       AND b.shipment_distinct_creation_ts_count > 1
        THEN 'BOOKING_MATCH_AMBIGUOUS_CREATION_TS'
      WHEN b.booking_number IS NOT NULL
       AND b.shipment_distinct_creation_ts_count = 1
       AND b.shipment_null_creation_ts_row_count > 0
        THEN 'BOOKING_MATCH_MIXED_MISSING_CREATION_TS'
      WHEN b.booking_number IS NOT NULL
        THEN 'BOOKING_MATCH_CREATION_TS_MISSING'
      ELSE 'NO_SHIPMENT_BOOKING_MATCH'
    END AS join_status,
    CASE
      WHEN n.booking_number IS NULL THEN 'NRT_BOOKING_NUMBER_MISSING'
      WHEN e.booking_tcr_key IS NOT NULL THEN NULL
      WHEN b.booking_number IS NULL THEN 'NO_BOOKING_NUMBER_OVERLAP'
      WHEN b.shipment_distinct_creation_ts_count > 1
        THEN 'MULTIPLE_SHIPMENT_CREATION_TIMESTAMPS'
      WHEN b.shipment_distinct_creation_ts_count = 1
       AND b.shipment_null_creation_ts_row_count > 0
        THEN 'MIXED_KNOWN_AND_MISSING_CREATION_TIMESTAMPS'
      WHEN n.tcr IS NULL THEN 'NRT_TCR_MISSING_AND_CREATION_TS_MISSING'
      ELSE 'TCR_MISMATCH_AND_CREATION_TS_MISSING'
    END AS unmatched_reason_code,
    CASE
      WHEN n.latest_snapshot_row_count > 1
        THEN 'AMBIGUOUS_LATEST_NRT_SNAPSHOT'
      WHEN e.booking_tcr_key IS NULL
       AND NOT (
         b.booking_number IS NOT NULL
         AND b.shipment_distinct_creation_ts_count = 1
         AND b.shipment_null_creation_ts_row_count = 0
       ) THEN 'NO_CONTROLLED_MATCH'
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count > 1
        THEN 'MULTIPLE_EXACT_KEY_CREATION_TIMESTAMPS'
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count = 1
       AND e.candidate_null_creation_ts_row_count > 0
        THEN 'MIXED_KNOWN_AND_MISSING_EXACT_KEY_TIMESTAMPS'
      WHEN e.booking_tcr_key IS NOT NULL
       AND e.candidate_creation_ts_count = 0
        THEN 'MATCHED_CREATION_TIMESTAMP_MISSING'
      WHEN e.booking_tcr_key IS NULL
       AND b.booking_record_created_at IS NULL
        THEN 'MATCHED_CREATION_TIMESTAMP_MISSING'
      WHEN n.tcr_cutoff IS NULL
        THEN 'TCR_CUTOFF_MISSING_OR_UNPARSEABLE'
      ELSE NULL
    END AS timing_exclusion_reason,
    b.booking_number IS NOT NULL AS has_booking_number_overlap,
    (
      e.booking_tcr_key IS NOT NULL
      OR (
        e.booking_tcr_key IS NULL
        AND b.booking_number IS NOT NULL
        AND b.shipment_distinct_creation_ts_count = 1
        AND b.shipment_null_creation_ts_row_count = 0
      )
    ) AS has_controlled_match
  FROM nrt_latest n
  LEFT JOIN exact_match e
    ON e.booking_tcr_key = n.booking_tcr_key
  LEFT JOIN shipment_booking_profile b
    ON b.booking_number = n.booking_number
  LEFT JOIN shipment_tcr_profile t
    ON t.booking_number = n.booking_number
),
precision_tagged AS (
  SELECT
    *,
    CASE
      WHEN tcr_cutoff IS NULL THEN 'MISSING_OR_UNPARSEABLE'
      WHEN tcr_cutoff_raw RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN 'DATE_ONLY'
      WHEN DATE_FORMAT(tcr_cutoff, 'HH:mm:ss') = '00:00:00'
        THEN 'MIDNIGHT_TIME_UNCONFIRMED'
      ELSE 'TIMESTAMP'
    END AS cutoff_precision_flag
  FROM resolved
),
timed AS (
  SELECT
    *,
    (
      has_controlled_match
      AND NOT has_ambiguous_latest_snapshot
      AND record_created_at IS NOT NULL
      AND tcr_cutoff IS NOT NULL
    ) AS is_valid_timing_record,
    (
      has_controlled_match
      AND NOT has_ambiguous_latest_snapshot
      AND record_created_at IS NOT NULL
      AND tcr_cutoff IS NOT NULL
      AND cutoff_precision_flag = 'TIMESTAMP'
    ) AS is_valid_hour_timing_record
  FROM precision_tagged
),
with_intervals AS (
  SELECT
    *,
    CASE
      WHEN is_valid_hour_timing_record THEN ROUND(
        (
          CAST(UNIX_TIMESTAMP(tcr_cutoff) AS DOUBLE)
          - CAST(UNIX_TIMESTAMP(record_created_at) AS DOUBLE)
        ) / 3600.0,
        2
      )
    END AS hours_before_tcr,
    CASE
      WHEN is_valid_timing_record
        THEN DATEDIFF(TO_DATE(tcr_cutoff), TO_DATE(record_created_at))
    END AS calendar_days_before_tcr
  FROM timed
),
with_metrics AS (
  SELECT
    *,
    CASE
      WHEN is_valid_hour_timing_record THEN ROUND(hours_before_tcr / 24.0, 3)
      WHEN is_valid_timing_record THEN CAST(calendar_days_before_tcr AS DOUBLE)
    END AS days_before_tcr,
    CASE
      WHEN NOT is_valid_timing_record THEN NULL
      WHEN is_valid_hour_timing_record THEN hours_before_tcr < 0
      WHEN calendar_days_before_tcr < 0 THEN TRUE
      WHEN calendar_days_before_tcr > 0 THEN FALSE
      ELSE NULL
    END AS is_after_cutoff,
    CASE
      WHEN NOT is_valid_timing_record THEN 'NOT_SCORABLE'
      WHEN is_valid_hour_timing_record THEN 'EXACT_TIMESTAMP'
      ELSE 'CALENDAR_DAY'
    END AS timing_granularity,
    (
      is_valid_timing_record
      AND NOT is_valid_hour_timing_record
      AND calendar_days_before_tcr = 0
    ) AS same_day_order_unknown
  FROM with_intervals
)
SELECT
  booking_tcr_key,
  booking_number,
  customer,
  service,
  svvd,
  tcr,
  week_num,
  booking_status,
  tcr_cutoff_raw,
  tcr_cutoff,
  selected_nrt_run_ts,
  nrt_snapshot_row_count,
  latest_snapshot_row_count,
  has_ambiguous_latest_snapshot,
  record_created_at,
  matched_shipment_tcr,
  matched_tcr_sources,
  matched_tcr_candidate_row_count,
  matched_tcr_creation_ts_count,
  matched_tcr_null_creation_ts_row_count,
  shipment_normalized_row_count,
  shipment_distinct_creation_ts_count,
  shipment_null_creation_ts_row_count,
  shipment_distinct_tcr_count,
  match_tier,
  match_method,
  join_status,
  unmatched_reason_code,
  timing_exclusion_reason,
  has_booking_number_overlap,
  has_controlled_match,
  is_valid_timing_record,
  is_valid_hour_timing_record,
  timing_granularity,
  same_day_order_unknown,
  hours_before_tcr,
  days_before_tcr,
  calendar_days_before_tcr,
  CASE
    WHEN NOT is_valid_timing_record THEN 'Not scorable'
    WHEN is_after_cutoff THEN 'After cutoff'
    WHEN days_before_tcr < 1 THEN 'Same day'
    WHEN days_before_tcr < 4 THEN '1-3 days'
    WHEN days_before_tcr < 8 THEN '4-7 days'
    WHEN days_before_tcr < 15 THEN '8-14 days'
    WHEN days_before_tcr < 31 THEN '15-30 days'
    ELSE '31+ days'
  END AS lead_time_bucket,
  CASE
    WHEN NOT is_valid_timing_record THEN 99
    WHEN is_after_cutoff THEN 0
    WHEN days_before_tcr < 1 THEN 1
    WHEN days_before_tcr < 4 THEN 2
    WHEN days_before_tcr < 8 THEN 3
    WHEN days_before_tcr < 15 THEN 4
    WHEN days_before_tcr < 31 THEN 5
    ELSE 6
  END AS lead_time_bucket_sort,
  is_after_cutoff,
  cutoff_precision_flag,
  TRUE AS creation_timestamp_is_proxy,
  'csal_shipment.rec_cre_dt_utc' AS creation_timestamp_source
FROM with_metrics;
