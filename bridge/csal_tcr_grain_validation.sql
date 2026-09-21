WITH nrt_base AS (
  SELECT
    NULLIF(TRIM(CAST(booking_number AS STRING)), '') AS booking_number,
    NULLIF(UPPER(TRIM(CAST(svvd AS STRING))), '') AS svvd,
    NULLIF(UPPER(TRIM(CAST(tcr AS STRING))), '') AS tcr,
    TRY_CAST(tcr_cutoff AS TIMESTAMP) AS tcr_cutoff_ts,
    TRY_CAST(run_date AS TIMESTAMP) AS run_ts
  FROM dev.crmi_gold.csal_teu_performance_nrt
),
nrt_history AS (
  SELECT
    *,
    COUNT(*) OVER (
      PARTITION BY booking_number, svvd, tcr
    ) AS nrt_rows,
    ROW_NUMBER() OVER (
      PARTITION BY booking_number, svvd, tcr
      ORDER BY run_ts DESC NULLS LAST
    ) AS rn
  FROM nrt_base
  WHERE booking_number IS NOT NULL
    AND svvd IS NOT NULL
    AND tcr IS NOT NULL
),
nrt_latest AS (
  SELECT *
  FROM nrt_history
  WHERE rn = 1
),
shipment_base AS (
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
shipment AS (
  SELECT
    booking_number,
    tcr,
    COUNT(*) AS shipment_rows,
    MIN(record_created_at) AS record_created_at
  FROM shipment_base
  WHERE booking_number IS NOT NULL
    AND tcr IS NOT NULL
  GROUP BY booking_number, tcr
),
joined AS (
  SELECT
    n.booking_number,
    n.svvd,
    n.tcr,
    n.nrt_rows,
    COALESCE(s.shipment_rows, 0) AS shipment_rows,
    TIMESTAMPDIFF(HOUR, s.record_created_at, n.tcr_cutoff_ts) AS lead_hours
  FROM nrt_latest n
  LEFT JOIN shipment s
    ON n.booking_number = s.booking_number
   AND n.tcr = s.tcr
)
SELECT
  CASE
    WHEN shipment_rows = 0 THEN 'UNMATCHED'
    WHEN nrt_rows = 1 AND shipment_rows = 1 THEN '1:1'
    WHEN nrt_rows = 1 THEN '1:M'
    WHEN shipment_rows = 1 THEN 'M:1'
    ELSE 'M:M'
  END AS raw_cardinality,
  COUNT(*) AS booking_svvd_tcr_keys,
  COUNT_IF(lead_hours < 0) AS after_cutoff_keys,
  MIN(lead_hours) AS minimum_lead_hours,
  MAX(lead_hours) AS maximum_lead_hours
FROM joined
GROUP BY 1
ORDER BY 1;
