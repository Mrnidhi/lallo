# Databricks notebook cell (Python). Paste the whole file into one Python cell.
# Scope: all services in CSAL booking detail. One shipment is counted once.
# The timestamp is CSAL shipment-record creation, not a confirmed booking event.

from datetime import datetime, timezone
from pyspark.sql import functions as F, Window
from pyspark import StorageLevel

AS_OF_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
FIRST_CUTOFF_UTC = "2026-06-01T00:00:00Z"  # explicit analysis period; edit if needed
FIRST_RECORD_UTC = "2026-05-01T00:00:00Z"  # covers the 28 days before the first cutoff
FOLLOWUP_DAYS = 14
BEFORE_DAYS = 28

print(
    f"As of {AS_OF_UTC} UTC | all services | cutoffs from {FIRST_CUTOFF_UTC} "
    f"through as-of minus {FOLLOWUP_DAYS} days"
)
print(f"Coverage denominator: current booking-detail shipments with detail records created from {FIRST_RECORD_UTC} through as-of.")
print("A record-creation date is a provisional timing proxy. Route and cutoff use current source rows.")

for _name in ("csal_timing_base", "csal_service_coverage", "csal_service_summary", "csal_daily_curve"):
    if _name in globals():
        try:
            globals()[_name].unpersist()
        except Exception:
            pass

csal_timing_base = spark.sql(f"""
WITH detail_raw AS (
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
                  AND SUBSTRING(corp_direction, 1, 1) IN ('N','S','E','W')
      THEN CONCAT(REGEXP_REPLACE(service, '-[NSEW]$', ''), '-',
                  corp_vessel, '-',
                  CASE WHEN LENGTH(corp_voyage) < 3
                       THEN LPAD(corp_voyage, 3, '0')
                       ELSE corp_voyage END, ' ',
                  SUBSTRING(corp_direction, 1, 1)) END AS corp_svvd,
    CASE WHEN first_service IS NOT NULL AND first_vessel IS NOT NULL
                  AND first_voyage IS NOT NULL
                  AND SUBSTRING(first_direction, 1, 1) IN ('N','S','E','W')
      THEN CONCAT(REGEXP_REPLACE(first_service, '-[NSEW]$', ''), '-',
                  first_vessel, '-',
                  CASE WHEN LENGTH(first_voyage) < 3
                       THEN LPAD(first_voyage, 3, '0')
                       ELSE first_voyage END, ' ',
                  SUBSTRING(first_direction, 1, 1)) END AS first_svvd
  FROM detail_raw
),
detail_ranked AS (
  SELECT *, DENSE_RANK() OVER (
    PARTITION BY shipment_num ORDER BY detail_updated_at DESC NULLS LAST
  ) AS current_rank
  FROM detail_routes WHERE shipment_num IS NOT NULL
),
detail_one AS (
  SELECT shipment_num,
    MAX(service) AS service, MAX(corp_svvd) AS corp_svvd,
    MAX(first_svvd) AS first_svvd, MAX(loading_port) AS loading_port,
    MAX(first_port) AS first_port,
    MAX(detail_sail_week) AS detail_sail_week,
    MIN(detail_record_created_at) AS detail_record_created_at,
    COUNT(*) AS current_detail_rows,
    COUNT(DISTINCT CONCAT_WS('||',
      COALESCE(service, '<null>'), COALESCE(corp_svvd, '<null>'),
      COALESCE(first_svvd, '<null>'), COALESCE(loading_port, '<null>'),
      COALESCE(first_port, '<null>'), COALESCE(detail_sail_week, '<null>')
    )) AS current_route_variants
  FROM detail_ranked WHERE current_rank = 1 GROUP BY shipment_num
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
    CASE WHEN use_dep_svvd = TRUE THEN NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST(dep_svvd AS STRING))), ' +', ' '), '')
         WHEN use_dep_svvd = FALSE THEN NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST(arr_svvd AS STRING))), ' +', ' '), '')
    END AS effective_svvd,
    NULLIF(UPPER(TRIM(CAST(sail_week AS STRING))), '') AS stop_sail_week,
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
  ) AS current_rank FROM stop_raw
),
stop_current AS (
  SELECT *, COUNT(*) OVER (PARTITION BY stop_identity) AS current_stop_rows
  FROM stop_ranked WHERE current_rank = 1
),
joined AS (
  SELECT d.*, sh.record_created_at, sh.distinct_creation_times,
    sh.missing_creation_rows,
    s.stop_id, s.stop_identity, s.current_stop_rows,
    s.stop_sail_week, s.cutoff_ts, s.stop_flags_ok
  FROM detail_one d
  LEFT JOIN shipment_one sh ON sh.shipment_num = d.shipment_num
  LEFT JOIN stop_current s ON s.effective_svvd = d.corp_svvd
                           AND s.stop_port = d.loading_port
),
rolled AS (
  SELECT shipment_num, service, corp_svvd, first_svvd, loading_port,
    first_port, detail_sail_week, current_detail_rows,
    current_route_variants, detail_record_created_at,
    record_created_at, distinct_creation_times,
    missing_creation_rows,
    COUNT(DISTINCT stop_identity) AS exact_stops,
    COUNT(DISTINCT stop_id) AS exact_stop_rows,
    MAX(current_stop_rows) AS max_stop_revision_rows,
    COUNT(DISTINCT cutoff_ts) AS distinct_cutoffs,
    MAX(cutoff_ts) AS cutoff_ts,
    MAX(stop_sail_week) AS stop_sail_week,
    MAX(CASE WHEN stop_identity IS NOT NULL AND stop_flags_ok = 0
             THEN 1 ELSE 0 END) AS flagged_stop
  FROM joined
  GROUP BY shipment_num, service, corp_svvd, first_svvd,
    loading_port, first_port, detail_sail_week, current_detail_rows,
    current_route_variants, detail_record_created_at,
    record_created_at, distinct_creation_times,
    missing_creation_rows
),
classified AS (
  SELECT *,
    CASE WHEN first_svvd IS NULL OR corp_svvd IS NULL
               OR first_port IS NULL OR loading_port IS NULL
           THEN 'ROUTE_TYPE_UNKNOWN'
         WHEN first_svvd = corp_svvd AND first_port = loading_port
           THEN 'DIRECT_SAME_LEG'
         ELSE 'DIFFERENT_LEGS' END AS route_class,
    CASE WHEN detail_sail_week IS NULL OR stop_sail_week IS NULL
           THEN 'WEEK_UNCONFIRMED'
         WHEN detail_sail_week = stop_sail_week THEN 'WEEK_AGREES'
         ELSE 'WEEK_DIFFERS' END AS week_check,
    CASE WHEN current_route_variants > 1 THEN 'DETAIL_ROUTE_TIE'
         WHEN corp_svvd IS NULL OR loading_port IS NULL THEN 'ROUTE_INCOMPLETE'
         WHEN exact_stops = 0 THEN 'NO_EXACT_VOYAGE_PORT_STOP'
         WHEN exact_stops > 1 THEN 'MULTIPLE_STOPS'
         WHEN exact_stop_rows > 1 OR max_stop_revision_rows > 1
           THEN 'STOP_REVISION_TIE'
         WHEN flagged_stop > 0 THEN 'STOP_FLAGS_REVIEW'
         WHEN distinct_cutoffs <> 1 THEN 'CUTOFF_MISSING_OR_AMBIGUOUS'
         ELSE 'UNIQUE_CURRENT_STOP' END AS match_status
  FROM rolled
),
eligible AS (
  SELECT *,
    CASE WHEN match_status = 'UNIQUE_CURRENT_STOP'
              AND route_class = 'DIRECT_SAME_LEG'
              AND distinct_creation_times = 1
              AND missing_creation_rows = 0
              AND cutoff_ts >= CAST('{FIRST_CUTOFF_UTC}' AS TIMESTAMP)
              AND cutoff_ts <= CAST('{AS_OF_UTC}' AS TIMESTAMP)
                               - INTERVAL {FOLLOWUP_DAYS} DAYS
         THEN TRUE ELSE FALSE END AS matured_direct_match
  FROM classified
)
SELECT *,
  CAST(FLOOR((CAST(record_created_at AS LONG) - CAST(cutoff_ts AS LONG))
             / 86400.0) AS INT) AS day_bucket_from_cutoff,
  CASE WHEN record_created_at < cutoff_ts THEN 'BEFORE'
       WHEN record_created_at > cutoff_ts THEN 'AFTER'
       WHEN record_created_at = cutoff_ts THEN 'AT CUTOFF'
  END AS exact_time_position
FROM eligible
WHERE detail_record_created_at >= CAST('{FIRST_RECORD_UTC}' AS TIMESTAMP)
  AND detail_record_created_at <= CAST('{AS_OF_UTC}' AS TIMESTAMP)
""").persist(StorageLevel.MEMORY_AND_DISK)

# The denominator comes from booking detail, so missing shipment records stay visible.
# Sail-week fields have different possible meanings and are a diagnostic, not a join.
csal_service_coverage = (
    csal_timing_base.groupBy("service")
    .agg(
        F.count("*").alias("source_shipments"),
        F.sum(F.when(F.col("match_status") == "UNIQUE_CURRENT_STOP", 1).otherwise(0)).alias("unique_current_stops"),
        F.sum(F.when(F.col("matured_direct_match"), 1).otherwise(0)).alias("matured_direct_matches"),
        F.sum(F.when(F.col("match_status") != "UNIQUE_CURRENT_STOP", 1).otherwise(0)).alias("unresolved_stop_match"),
        F.sum(F.when(F.col("route_class") == "DIFFERENT_LEGS", 1).otherwise(0)).alias("different_legs"),
        F.sum(F.when(F.col("week_check") == "WEEK_AGREES", 1).otherwise(0)).alias("week_agrees"),
        F.sum(F.when(F.col("week_check") == "WEEK_DIFFERS", 1).otherwise(0)).alias("week_differs"),
        F.sum(F.when(F.col("week_check") == "WEEK_UNCONFIRMED", 1).otherwise(0)).alias("week_unconfirmed"),
        F.sum(F.when(F.col("record_created_at").isNull(), 1).otherwise(0)).alias("shipment_creation_missing"),
    )
    .withColumn("unique_stop_coverage_pct", F.round(100 * F.col("unique_current_stops") / F.col("source_shipments"), 1))
    .withColumn("matured_direct_coverage_pct", F.round(100 * F.col("matured_direct_matches") / F.col("source_shipments"), 1))
    .orderBy(F.desc("source_shipments"))
)

csal_comparable = csal_timing_base.filter(
    F.col("matured_direct_match")
    & F.col("day_bucket_from_cutoff").between(-BEFORE_DAYS, FOLLOWUP_DAYS - 1)
)

csal_service_summary = (
    csal_comparable.groupBy("service")
    .agg(
        F.count("*").alias("records_in_28_before_14_after_window"),
        F.sum(F.when(F.col("exact_time_position") == "BEFORE", 1).otherwise(0)).alias("before_cutoff"),
        F.sum(F.when(F.col("exact_time_position") == "AFTER", 1).otherwise(0)).alias("after_cutoff"),
        F.sum(F.when(F.col("exact_time_position") == "AT CUTOFF", 1).otherwise(0)).alias("at_cutoff"),
        F.expr("percentile_approx((cast(record_created_at as long) - cast(cutoff_ts as long)) / 86400.0, 0.5)").alias("median_days_relative_to_cutoff"),
        F.sum(F.when(F.col("week_check") == "WEEK_AGREES", 1).otherwise(0)).alias("week_agrees"),
        F.sum(F.when(F.col("week_check") == "WEEK_DIFFERS", 1).otherwise(0)).alias("week_differs"),
        F.sum(F.when(F.col("week_check") == "WEEK_UNCONFIRMED", 1).otherwise(0)).alias("week_unconfirmed"),
    )
    .withColumn("after_pct_of_comparable", F.round(100 * F.col("after_cutoff") / F.col("records_in_28_before_14_after_window"), 1))
    .join(csal_service_coverage.select("service", "source_shipments", "matured_direct_matches"), "service", "left")
    .orderBy(F.desc("records_in_28_before_14_after_window"))
)

daily_by_service = (
    csal_comparable.groupBy("service", "day_bucket_from_cutoff")
    .agg(F.count("*").alias("records_created"))
)
daily_all = (
    csal_comparable.groupBy("day_bucket_from_cutoff")
    .agg(F.count("*").alias("records_created"))
    .withColumn("service", F.lit("ALL SERVICES"))
    .select("service", "day_bucket_from_cutoff", "records_created")
)
daily_counts = daily_by_service.unionByName(daily_all)
services = daily_counts.select("service").distinct()
days = spark.range(-BEFORE_DAYS, FOLLOWUP_DAYS).select(F.col("id").cast("int").alias("day_bucket_from_cutoff"))
daily_complete = (
    services.crossJoin(days)
    .join(daily_counts, ["service", "day_bucket_from_cutoff"], "left")
    .fillna({"records_created": 0})
)
w = Window.partitionBy("service").orderBy("day_bucket_from_cutoff").rowsBetween(Window.unboundedPreceding, Window.currentRow)
service_totals = daily_counts.groupBy("service").agg(F.sum("records_created").alias("service_window_total"))
csal_daily_curve = (
    daily_complete.join(service_totals, "service")
    .withColumn("cumulative_records", F.sum("records_created").over(w))
    .withColumn("cumulative_pct_of_window", F.round(100 * F.col("cumulative_records") / F.col("service_window_total"), 1))
    .orderBy("service", "day_bucket_from_cutoff")
)
csal_all_service_curve = csal_daily_curve.filter(F.col("service") == "ALL SERVICES")
top_services = (
    service_totals.filter(F.col("service") != "ALL SERVICES")
    .orderBy(F.desc("service_window_total"))
    .limit(8)
    .select("service")
)
csal_top_service_curve = csal_daily_curve.join(top_services, "service", "inner")

print("1. Coverage by service: this is the denominator for judging representativeness.")
display(csal_service_coverage)
print("2. Timing by service, using only matured direct-route records in the same 28/14-day window.")
display(csal_service_summary)
print("3. Pooled daily curve. Negative day buckets are before cutoff; 0 is the first 24 hours after cutoff.")
display(csal_all_service_curve)
print("4. The eight services with the most comparable records. Full service data remains in csal_daily_curve.")
display(csal_top_service_curve)
print("Current routes and cutoff schedules may differ from the historical state. Sail-week agreement, disagreement and missing values are shown separately; the week fields are not assumed equivalent.")
print("These outputs describe CSAL record creation. They do not establish original booking time, actual swaps, or a recommendation policy.")
