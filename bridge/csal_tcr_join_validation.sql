-- Read-only validation: distinct booking-number coverage between NRT and CSAL shipment.
WITH n AS (
  SELECT DISTINCT CAST(booking_number AS STRING) AS booking_key
  FROM dev.crmi_gold.csal_teu_performance_nrt
  WHERE booking_number IS NOT NULL
),
s AS (
  SELECT DISTINCT CAST(shipment_number AS STRING) AS booking_key
  FROM datasources.csal.csal_shipment
  WHERE shipment_number IS NOT NULL
)
SELECT
  COUNT(*) AS nrt_bookings,
  COUNT(s.booking_key) AS matched_bookings,
  COUNT(*) - COUNT(s.booking_key) AS unmatched_bookings,
  ROUND(100.0 * COUNT(s.booking_key) / COUNT(*), 2) AS join_coverage_pct
FROM n
LEFT JOIN s ON n.booking_key = s.booking_key;
