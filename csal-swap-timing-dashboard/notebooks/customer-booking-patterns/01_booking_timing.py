# Databricks notebook source
# Paste this whole file into a Python cell. Run 02 next, or use the combined file.
from datetime import datetime, timezone
from pyspark.sql import functions as F

YEAR = 2026
SERVICES = None                  # None = all services; example: ["PNW5", "PNW1"]
DAYS_BEFORE = 56
DAYS_AFTER = 14
MIN_BOOKINGS = 20
MIN_VOYAGES = 3
MIN_CUSTOMERS_PER_GROUP = 5
MAX_GROUPS = 8
MIN_SILHOUETTE = 0.35
STABILITY_SHIFT_DAYS = 7
CHART_SERVICE = None             # None = service with the most eligible customers.
CHART_CUSTOMER = None            # Optional name to focus the customer comparison.
MAX_CUSTOMERS_ON_CHART = 25
EXCLUDE_CUSTOMER_NAMES = ["Open Customers", "APN Unassigned"]


def sql_text(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def clean_customer(value):
    return " ".join(str(value).split()).upper() if value is not None else ""


def booking_timing_sql(year, days_before, days_after, as_of, services=None):
    if not (2000 <= year <= 2100 and 1 <= days_before <= 365 and 1 <= days_after <= 90):
        raise ValueError("Check YEAR, DAYS_BEFORE (1–365), and DAYS_AFTER (1–90).")
    service_clause = "TRUE"
    if services is not None:
        if isinstance(services, str) or not services:
            raise ValueError('SERVICES must be None or a list such as ["PNW5"].')
        service_clause = "service IN (" + ",".join(
            sql_text(str(x).strip().upper()) for x in services
        ) + ")"
    # Customer aliases are not merged. Only case and whitespace are normalized.
    name = "TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(CAST(ccp_cus_nme AS STRING), CHAR(9), ' '), CHAR(10), ' '), CHAR(13), ' '), ' +', ' '))"
    return f"""
WITH params AS (
  SELECT TIMESTAMP '{year}-01-01T00:00:00Z' AS year_start,
         LEAST(TIMESTAMP '{year + 1}-01-01T00:00:00Z',
               TIMESTAMP '{as_of}') AS observation_end
),
detail_raw AS (
  SELECT DISTINCT
    NULLIF(UPPER(TRIM(CAST(shipment_num AS STRING))), '') AS shipment_num,
    NULLIF({name}, '') AS customer,
    NULLIF(UPPER({name}), '') AS customer_key,
    REGEXP_REPLACE(NULLIF(UPPER(TRIM(corp_svc_cde)), ''), '-[NSEW]$', '') AS service,
    NULLIF(UPPER(TRIM(corp_vsl_cde)), '') AS vessel,
    NULLIF(UPPER(TRIM(corp_voy_num)), '') AS voyage,
    SUBSTRING(UPPER(TRIM(corp_voy_dir)), 1, 1) AS direction,
    REGEXP_REPLACE(NULLIF(UPPER(TRIM(f_load_svc_cde)), ''), '-[NSEW]$', '') AS first_service,
    NULLIF(UPPER(TRIM(f_load_vsl_cde)), '') AS first_vessel,
    NULLIF(UPPER(TRIM(f_load_voy_num)), '') AS first_voyage,
    SUBSTRING(UPPER(TRIM(f_load_dir)), 1, 1) AS first_direction,
    NULLIF(UPPER(TRIM(fpol_port_cde)), '') AS first_port,
    NULLIF(UPPER(TRIM(lpol_port_cde)), '') AS loading_port,
    TRIM(shipment_status) AS current_shipment_status,
    CASE WHEN CAST(lpol_etd_iodt_utc AS STRING) RLIKE '^[0-9]{{14}}([.][0-9]{{1,9}})?$'
      THEN TRY_CAST(CONCAT(SUBSTRING(lpol_etd_iodt_utc, 1, 4), '-',
        SUBSTRING(lpol_etd_iodt_utc, 5, 2), '-', SUBSTRING(lpol_etd_iodt_utc, 7, 2), 'T',
        SUBSTRING(lpol_etd_iodt_utc, 9, 2), ':', SUBSTRING(lpol_etd_iodt_utc, 11, 2), ':',
        SUBSTRING(lpol_etd_iodt_utc, 13), 'Z') AS TIMESTAMP) END AS loading_departure,
    COALESCE(TRY_CAST(rec_upd_dt_utc AS TIMESTAMP),
             TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS updated_at
  FROM datasources.csal.csal_booking_detail
  WHERE shipment_num IS NOT NULL
),
routes AS (
  SELECT *,
    CASE WHEN service IS NOT NULL AND vessel IS NOT NULL AND voyage IS NOT NULL
              AND direction IN ('N','S','E','W')
      THEN CONCAT(service, '-', vessel, '-',
        CASE WHEN LENGTH(voyage) < 3 THEN LPAD(voyage, 3, '0') ELSE voyage END,
        ' ', direction) END AS svvd,
    CASE WHEN first_service IS NOT NULL AND first_vessel IS NOT NULL
              AND first_voyage IS NOT NULL AND first_direction IN ('N','S','E','W')
      THEN CONCAT(first_service, '-', first_vessel, '-',
        CASE WHEN LENGTH(first_voyage) < 3 THEN LPAD(first_voyage, 3, '0') ELSE first_voyage END,
        ' ', first_direction) END AS first_svvd,
    DENSE_RANK() OVER (PARTITION BY shipment_num ORDER BY updated_at DESC NULLS LAST) AS revision
  FROM detail_raw
  WHERE shipment_num IS NOT NULL
),
current_detail AS (
  SELECT shipment_num, MAX(customer) AS customer, MAX(customer_key) AS customer_key,
    MAX(service) AS service, MAX(svvd) AS svvd, MAX(first_svvd) AS first_svvd,
    MAX(first_port) AS first_port, MAX(loading_port) AS loading_port,
    MAX(loading_departure) AS loading_departure,
    MAX(current_shipment_status) AS current_shipment_status,
    COUNT(DISTINCT TO_JSON(NAMED_STRUCT(
      'customer', customer_key, 'service', service, 'svvd', svvd,
      'first_svvd', first_svvd, 'first_port', first_port, 'port', loading_port,
      'departure', loading_departure))) AS context_versions
  FROM routes WHERE revision = 1
  GROUP BY shipment_num
),
shipment_times AS (
  SELECT UPPER(TRIM(CAST(s.shipment_number AS STRING))) AS shipment_num,
    MIN(TRY_CAST(s.rec_cre_dt_utc AS TIMESTAMP)) AS booked_at,
    MAX(TRY_CAST(s.rec_cre_dt_utc AS TIMESTAMP)) AS last_creation_value,
    COUNT(DISTINCT TRY_CAST(s.rec_cre_dt_utc AS TIMESTAMP)) AS creation_values,
    SUM(CASE WHEN TRY_CAST(s.rec_cre_dt_utc AS TIMESTAMP) IS NULL THEN 1 ELSE 0 END) AS missing_times
  FROM datasources.csal.csal_shipment s
  INNER JOIN current_detail d ON UPPER(TRIM(CAST(s.shipment_number AS STRING))) = d.shipment_num
  GROUP BY UPPER(TRIM(CAST(s.shipment_number AS STRING)))
),
scope AS (
  SELECT d.*, t.booked_at, t.creation_values, t.missing_times,
    p.year_start, p.observation_end
  FROM current_detail d
  LEFT JOIN shipment_times t ON d.shipment_num = t.shipment_num
  CROSS JOIN params p
  WHERE {service_clause}
    AND (t.booked_at IS NULL OR t.creation_values <> 1 OR t.missing_times > 0
         OR (t.booked_at >= p.year_start AND t.booked_at < p.observation_end))
),
stop_raw AS (
  SELECT DISTINCT CAST(id AS STRING) AS stop_id,
    COALESCE(NULLIF(UPPER(TRIM(msg_business_key)), ''), CONCAT('ID:', CAST(id AS STRING))) AS stop_key,
    UPPER(TRIM(port_code)) AS port,
    CASE WHEN use_dep_svvd = TRUE THEN REGEXP_REPLACE(UPPER(TRIM(dep_svvd)), ' +', ' ')
         WHEN use_dep_svvd = FALSE THEN REGEXP_REPLACE(UPPER(TRIM(arr_svvd)), ' +', ' ')
    END AS svvd,
    TRY_CAST(tcr_cutoff_date AS TIMESTAMP) AS cutoff,
    TRY_CAST(voy_dep_dt_utc AS TIMESTAMP) AS departure,
    CASE WHEN is_load_allowed = TRUE AND is_omitted = FALSE
              AND is_tentative_schedule = FALSE AND is_vms = FALSE
              AND is_phase_out = FALSE AND private_call = FALSE
         THEN 1 ELSE 0 END AS flags_ok,
    COALESCE(TRY_CAST(rec_upd_dt_utc AS TIMESTAMP), TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS updated_at
  FROM datasources.csal.csal_voy_stop_dtl
),
stop_ranked AS (
  SELECT *, DENSE_RANK() OVER (PARTITION BY stop_key ORDER BY updated_at DESC NULLS LAST) AS revision
  FROM stop_raw
),
stops AS (
  SELECT *, COUNT(*) OVER (PARTITION BY stop_key) AS revision_rows
  FROM stop_ranked WHERE revision = 1
),
candidates AS (
  SELECT b.shipment_num, s.*,
    CASE WHEN b.loading_departure = s.departure THEN 1 ELSE 0 END AS departure_matches
  FROM scope b
  INNER JOIN stops s ON b.svvd = s.svvd AND b.loading_port = s.port
),
candidate_counts AS (
  SELECT shipment_num, COUNT(*) AS candidate_rows,
    SUM(departure_matches) AS exact_departure_rows
  FROM candidates GROUP BY shipment_num
),
chosen AS (
  SELECT c.* FROM candidates c
  INNER JOIN candidate_counts n ON c.shipment_num = n.shipment_num
  WHERE n.candidate_rows = 1
     OR (n.exact_departure_rows = 1 AND c.departure_matches = 1)
),
classified AS (
  SELECT b.*, s.stop_key, s.cutoff,
    (UNIX_MICROS(b.booked_at) - UNIX_MICROS(s.cutoff)) / 86400000000.0 AS days_from_cutoff,
    CASE
      WHEN b.booked_at IS NULL OR b.creation_values <> 1 OR b.missing_times <> 0
        THEN 'Booking time unresolved; year not assigned'
      WHEN b.context_versions <> 1 THEN 'Conflicting current customer or route'
      WHEN b.customer_key IS NULL THEN 'Customer name missing'
      WHEN b.svvd IS NULL OR b.first_svvd IS NULL OR b.loading_port IS NULL OR b.first_port IS NULL
        THEN 'Route fields missing'
      WHEN b.svvd <> b.first_svvd OR b.loading_port <> b.first_port
        THEN 'Connecting route; separate leg cutoff needed'
      WHEN n.candidate_rows IS NULL THEN 'No matching voyage and loading port'
      WHEN s.stop_key IS NULL OR s.revision_rows <> 1 THEN 'More than one possible stop or revision'
      WHEN s.flags_ok <> 1 THEN 'Omitted or unavailable loading call'
      WHEN s.cutoff IS NULL THEN 'Cutoff missing or unreadable'
      WHEN s.cutoff < b.year_start + INTERVAL {days_before} DAYS
        THEN 'Full pre-cutoff window not inside selected year'
      WHEN s.cutoff + INTERVAL {days_after} DAYS > b.observation_end
        THEN 'Full post-cutoff window not yet observed'
      WHEN b.booked_at < s.cutoff - INTERVAL {days_before} DAYS THEN 'Booked earlier than comparison window'
      WHEN b.booked_at >= s.cutoff + INTERVAL {days_after} DAYS THEN 'Booked later than comparison window'
      ELSE 'Included'
    END AS coverage_status
  FROM scope b
  LEFT JOIN candidate_counts n ON b.shipment_num = n.shipment_num
  LEFT JOIN chosen s ON b.shipment_num = s.shipment_num
)
SELECT shipment_num, customer, customer_key, service, svvd, loading_port,
       current_shipment_status, coverage_status,
       UNIX_MICROS(booked_at) AS booked_at_us, UNIX_MICROS(cutoff) AS cutoff_us,
       days_from_cutoff, CAST(FLOOR(days_from_cutoff) AS INT) AS day_from_cutoff
FROM classified
"""


def prepare_booking_timing():
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if datetime.now(timezone.utc).year < YEAR:
        raise ValueError("YEAR is in the future.")
    previous = globals().get("CUSTOMER_TIMING")
    if isinstance(previous, dict) and previous.get("frame") is not None:
        previous["frame"].unpersist()
    frame = spark.sql(booking_timing_sql(YEAR, DAYS_BEFORE, DAYS_AFTER, as_of, SERVICES))
    excluded_names = [clean_customer(x) for x in EXCLUDE_CUSTOMER_NAMES]
    if excluded_names:
        frame = frame.withColumn("coverage_status", F.when(
            (F.col("coverage_status") == "Included") & F.col("customer_key").isin(excluded_names),
            F.lit("Pooled allocation name; not an individual customer")
        ).otherwise(F.col("coverage_status")))
    frame = frame.cache()
    coverage = frame.groupBy("service", "coverage_status").count().orderBy("service", "coverage_status")
    coverage_rows = coverage.collect()  # Materializes the shared data once.
    print(f"Read at {as_of} | Booking year: {YEAR} | Services: {SERVICES or 'All'}")
    print(f"Comparison: {DAYS_BEFORE} days before to {DAYS_AFTER} days after TCR cutoff.")
    print("Both ends must fall inside the selected year through the read time.")
    print("Booking timestamp: csal_shipment.rec_cre_dt_utc, confirmed by the user.")
    print("One booking per shipment; all current shipment statuses are retained.")
    print("Current vessel/port assignment and latest available cutoffs are used.")
    print("Connecting routes remain outside this version; missing matches stay in coverage.")
    print("BEGIN COVERAGE\nservice\tstatus\tshipments")
    for row in coverage_rows:
        print(f"{row['service'] or '[missing]'}\t{row['coverage_status']}\t{row['count']}")
    print("END COVERAGE")
    return {"frame": frame, "coverage": coverage, "as_of": as_of,
            "settings": {"year": YEAR, "services": SERVICES,
                         "days_before": DAYS_BEFORE, "days_after": DAYS_AFTER}}


CUSTOMER_TIMING = prepare_booking_timing()
