# Databricks notebook source
# Paste the whole file into one Python cell. No earlier cells are required.
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
from pyspark.sql import functions as F

YEAR = 2026
SERVICES = None             # All services; or a list such as ["PNW1", "PNW5"].
CUSTOMER = None             # Optional exact name, ignoring case and extra spaces.
CHART_SERVICE = None       # Optional service to display first.
DAYS_BEFORE = 56
DAYS_AFTER = 14
AUDIT_TIMEZONE = None      # Set only when the audit timestamp timezone is confirmed.
MAX_AUDIT_ROWS = 200000
MAX_BOOKING_ROWS_SHOWN = 20000
EXCLUDE_CUSTOMER_NAMES = ["Open Customers", "APN Unassigned"]

def sql_text(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"

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


def extra_space_sql(year, services=None, customer=None):
    name = "TRIM(REGEXP_REPLACE(REPLACE(REPLACE(REPLACE(CAST(customer AS STRING), CHAR(9), ' '), CHAR(10), ' '), CHAR(13), ' '), ' +', ' '))"
    scope = "TRUE"
    if services is not None:
        if isinstance(services, str) or not services:
            raise ValueError("SERVICES must be None or a nonempty list.")
        scope += " AND (p.service IN (" + ",".join(sql_text(str(s).strip().upper()) for s in services) + ") OR p.context_versions <> 1 OR p.service IS NULL)"
    if customer:
        scope += " AND (p.customer_key = " + sql_text(clean_customer(customer)) + " OR p.context_versions <> 1 OR p.customer_key IS NULL)"
    return f"""
WITH context_rows AS (
  SELECT DISTINCT CAST(csal_id AS STRING) AS plan_id,
    NULLIF({name}, '') AS customer,
    NULLIF(UPPER({name}), '') AS customer_key,
    REGEXP_REPLACE(NULLIF(UPPER(TRIM(service)), ''), '-[NSEW]$', '') AS service,
    NULLIF(UPPER(TRIM(vessel_voyage)), '') AS short_voyage,
    NULLIF(UPPER(TRIM(agreement)), '') AS agreement
  FROM datasources.csal.csal_change_log
  WHERE csal_id IS NOT NULL
),
plan_context AS (
  SELECT plan_id, MIN(customer) AS customer, MAX(customer_key) AS customer_key,
    MAX(service) AS service,
    COUNT(DISTINCT TO_JSON(NAMED_STRUCT('customer', customer_key, 'service', service))) AS context_versions,
    CASE WHEN COUNT(DISTINCT COALESCE(short_voyage, '<missing>')) = 1
         THEN MAX(short_voyage) END AS short_voyage,
    CASE WHEN COUNT(DISTINCT COALESCE(agreement, '<missing>')) = 1
         THEN MAX(agreement) END AS agreement
  FROM context_rows GROUP BY plan_id
),
audit_ids AS (
  SELECT DISTINCT uuid
  FROM datasources.csal.csal_audit_trail
  WHERE LOWER(REGEXP_REPLACE(change_field, '[^a-zA-Z]', '')) = 'requestedteu'
    AND SUBSTRING(TRIM(date_time), 1, 4) = '{year}' AND uuid IS NOT NULL
),
audit_distinct AS (
  SELECT DISTINCT CAST(uuid AS STRING) AS audit_id, CAST(csal_id AS STRING) AS plan_id,
    LOWER(TRIM(type)) AS action_type,
    LOWER(REGEXP_REPLACE(change_field, '[^a-zA-Z]', '')) AS field_key,
    TRIM(change_from) AS old_raw, TRIM(change_to) AS new_raw,
    TRIM(user_name) AS recorded_by, TRIM(date_time) AS raw_event_time
  FROM datasources.csal.csal_audit_trail
  WHERE uuid IN (SELECT uuid FROM audit_ids)
     OR (uuid IS NULL AND SUBSTRING(TRIM(date_time), 1, 4) = '{year}'
         AND LOWER(REGEXP_REPLACE(change_field, '[^a-zA-Z]', '')) = 'requestedteu')
),
audit_checked AS (
  SELECT *, COUNT(*) OVER (PARTITION BY audit_id) AS id_versions,
    COUNT(*) OVER (PARTITION BY plan_id, raw_event_time, action_type,
                               field_key, old_raw, new_raw, recorded_by) AS same_edit_rows,
    TRY_CAST(old_raw AS DECIMAL(18,6)) AS previous_requested_teu,
    TRY_CAST(new_raw AS DECIMAL(18,6)) AS requested_total_teu
  FROM audit_distinct
),
joined AS (
  SELECT a.*, p.customer, p.customer_key, p.service, p.short_voyage, p.agreement,
    p.context_versions, a.requested_total_teu - a.previous_requested_teu AS extra_teu,
    CASE
      WHEN a.audit_id IS NULL OR a.plan_id IS NULL OR a.id_versions <> 1 THEN 'Audit identity unresolved'
      WHEN a.same_edit_rows <> 1 THEN 'Repeated edit under different audit IDs'
      WHEN p.context_versions IS NULL THEN 'No plan customer history available'
      WHEN p.context_versions <> 1 THEN 'Customer or service varies in available plan history'
      WHEN p.customer_key IS NULL OR p.service IS NULL THEN 'Plan customer or service missing'
      WHEN a.action_type NOT IN ('grid edit', 'multi edit') OR a.action_type IS NULL
        THEN 'Other action; not counted as a direct request edit'
      WHEN a.recorded_by IS NULL OR TRIM(a.recorded_by) = '' OR LOWER(a.recorded_by) = 'system'
        THEN 'System or unidentified editor'
      WHEN a.old_raw IS NULL OR a.old_raw = '' THEN 'Initial value; not an extra-space increase'
      WHEN a.previous_requested_teu IS NULL OR a.requested_total_teu IS NULL
        THEN 'Non-numeric or missing quantity'
      WHEN a.previous_requested_teu < 0 OR a.requested_total_teu < 0 THEN 'Negative quantity'
      WHEN a.requested_total_teu <= a.previous_requested_teu THEN 'Decrease or unchanged request'
      ELSE 'Positive requested-space edit'
    END AS evidence_status
  FROM audit_checked a
  LEFT JOIN plan_context p ON p.plan_id = a.plan_id
  WHERE a.field_key = 'requestedteu'
    AND SUBSTRING(a.raw_event_time, 1, 4) = '{year}'
    AND ({scope})
)
SELECT * FROM joined
"""


def parse_audit_time(raw, zone_name=None):
    """Preserve recorded wall time; UTC exists only with an offset or confirmed zone."""
    value = str(raw or "").strip()
    compact = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?", value, re.I)
    if compact:
        y, mo, d, h, minute, second, fraction, offset = compact.groups()
        value = f"{y}-{mo}-{d}T{h}:{minute}:{second}{fraction or ''}{offset or ''}"
    if not re.search(r"[T ]\d{2}:\d{2}:\d{2}", value):
        return None, None, "Timestamp unreadable"
    try:
        value = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value)
        parsed = datetime.fromisoformat(re.sub(r"[zZ]$", "+00:00", value))
    except ValueError:
        return None, None, "Timestamp unreadable"
    recorded = parsed.replace(tzinfo=None)
    if parsed.tzinfo is not None:
        return recorded, parsed.astimezone(timezone.utc), "Explicit timezone offset"
    if not zone_name:
        return recorded, None, "Timezone unconfirmed; recorded clock only"
    zone = ZoneInfo(zone_name)
    first, second = parsed.replace(tzinfo=zone, fold=0), parsed.replace(tzinfo=zone, fold=1)
    if (first.utcoffset() != second.utcoffset() or
        first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != parsed):
        return recorded, None, "Ambiguous or nonexistent local time"
    return recorded, first.astimezone(timezone.utc), "Configured audit timezone"


def classify_event_times(events, zone_name=None, as_of=None):
    result = events.copy()
    parsed = [parse_audit_time(value, zone_name) for value in result.raw_event_time]
    result["recorded_clock"] = [p[0] for p in parsed]
    result["event_time_utc"] = [p[1].isoformat() if p[1] else None for p in parsed]
    result["time_basis"] = [p[2] for p in parsed]
    positive = result.evidence_status == "Positive requested-space edit"
    unreadable = result.recorded_clock.isna()
    result.loc[positive & unreadable, "evidence_status"] = "Positive edit; timestamp unreadable"
    if as_of:
        for index, (_, utc, _) in zip(result.index, parsed):
            if utc and utc > as_of and result.at[index, "evidence_status"] == "Positive requested-space edit":
                result.at[index, "evidence_status"] = "Positive edit; timestamp after read time"
    for field in ("previous_requested_teu", "requested_total_teu", "extra_teu"):
        result[field] = pd.to_numeric(result[field], errors="coerce")
    return result


def summarize_extra_space(events):
    columns = ["service", "customer_key", "customer", "recorded_increases", "plans",
               "min_extra_teu", "median_extra_teu", "max_extra_teu",
               "min_requested_total_teu", "median_requested_total_teu", "max_requested_total_teu"]
    valid = events[events.evidence_status == "Positive requested-space edit"]
    if valid.empty:
        return pd.DataFrame(columns=columns)
    return valid.groupby(["service", "customer_key"], as_index=False).agg(
        customer=("customer", "min"), recorded_increases=("audit_id", "size"),
        plans=("plan_id", "nunique"), min_extra_teu=("extra_teu", "min"),
        median_extra_teu=("extra_teu", "median"), max_extra_teu=("extra_teu", "max"),
        min_requested_total_teu=("requested_total_teu", "min"),
        median_requested_total_teu=("requested_total_teu", "median"),
        max_requested_total_teu=("requested_total_teu", "max"))


def plot_booking_and_space(daily, events, customer, service, before=56, after=14):
    navy, red, grey = "#203D60", "#D20A2E", "#6C7681"
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.5), gridspec_kw={"hspace": 0.7})
    ax = axes[0]
    days = np.arange(-before, after)
    if daily.empty:
        ax.text(0.5, 0.5, "No bookings with a usable cutoff in this comparison window",
                ha="center", va="center", transform=ax.transAxes, color=grey)
    else:
        counts = daily.set_index("day_from_cutoff").bookings.reindex(days, fill_value=0)
        ax.plot(days, counts, color=navy, lw=1.8)
    ax.axvline(0, color=red, lw=1.2, linestyle="--")
    ax.set_title("When bookings are created", loc="left", color=navy, fontweight="bold")
    ax.set_xlabel("Days from TCR cutoff · 0 = cutoff")
    ax.set_ylabel("Bookings per day")
    ax.set_xlim(-before, after)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax = axes[1]
    if events.empty:
        ax.text(0.5, 0.5, "No qualifying recorded increases found\nThis does not establish that no extra space was requested.",
                ha="center", va="center", transform=ax.transAxes, color=grey)
        ax.set_xticks([])
    else:
        # Use UTC only when every displayed event can be aligned to UTC.
        all_utc = events.event_time_utc.notna().all()
        dates = pd.to_datetime(events.event_time_utc, utc=True) if all_utc else pd.to_datetime(events.recorded_clock)
        xs = mdates.date2num(dates.to_list())
        ax.vlines(xs, 0, events.extra_teu.to_numpy(dtype=float), color=red, lw=1.2, alpha=0.8)
        ax.scatter(xs, events.extra_teu, color=red, s=28, zorder=3)
        if len(set(xs)) == 1:
            ax.set_xlim(xs[0] - 1, xs[0] + 1)
        else:
            ax.margins(x=0.05)
        locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        low, med, high = events.extra_teu.min(), events.extra_teu.median(), events.extra_teu.max()
        ax.text(0.0, 1.05, f"Added space per edit: min {low:g} · median {med:g} · max {high:g} TEU",
                transform=ax.transAxes, fontsize=10, color=grey)
        ax.set_xlabel("Recorded edit time (UTC)" if all_utc else "Recorded edit date · timezone unconfirmed or unresolved")
    ax.set_title("Recorded increases to requested space", loc="left", color=navy, fontweight="bold", pad=30)
    ax.set_ylabel("Added TEU per edit")
    ax.set_ylim(bottom=0)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#E5E9EF", lw=0.6)
    fig.suptitle(f"{customer}\n{service} · Booking and requested-space history",
                 x=0.09, y=0.99, ha="left", fontsize=14, color=navy, fontweight="bold")
    fig.text(0.09, 0.015, "Requested-space edits are recorded plan changes, not confirmed customer submissions.\n"
             "The two panels use different time axes; no request-to-cutoff timing is inferred.", color=grey, fontsize=9)
    fig.subplots_adjust(top=0.85, bottom=0.13, left=0.09, right=0.98)
    plt.show()
    plt.close(fig)


def run_booking_and_space():
    as_of = datetime.now(timezone.utc)
    if YEAR > as_of.year:
        raise ValueError("YEAR is in the future.")
    if AUDIT_TIMEZONE:
        ZoneInfo(AUDIT_TIMEZONE)
    previous = globals().get("CUSTOMER_SPACE_RESULTS")
    if isinstance(previous, dict) and previous.get("booking_frame") is not None:
        previous["booking_frame"].unpersist()
    bookings = spark.sql(booking_timing_sql(YEAR, DAYS_BEFORE, DAYS_AFTER,
                                          as_of.strftime("%Y-%m-%dT%H:%M:%SZ"), SERVICES))
    if CUSTOMER:
        bookings = bookings.filter(F.col("customer_key") == clean_customer(CUSTOMER))
    pooled = [clean_customer(x) for x in EXCLUDE_CUSTOMER_NAMES]
    if pooled:
        bookings = bookings.withColumn("coverage_status", F.when(
            (F.col("coverage_status") == "Included") & F.col("customer_key").isin(pooled),
            F.lit("Pooled name; not an individual customer")).otherwise(F.col("coverage_status")))
    bookings = bookings.cache()
    print(f"Booking year {YEAR} | Request-edit year as recorded: {YEAR} | Services: {SERVICES or 'All'}")
    print(f"Booking comparison window: −{DAYS_BEFORE} to +{DAYS_AFTER} days; both ends must be observed.")
    print("Booking time uses the confirmed shipment creation field. Routes and cutoffs are latest available.")
    print("Extra space means new requested TEU minus previous requested TEU when the difference is positive.")
    print("This is an increase in the requested amount, not necessarily an increase above approved allocation.")
    print("\nBooking coverage")
    display(bookings.groupBy("service", "coverage_status").count().orderBy("service", "coverage_status"))
    included = bookings.filter(F.col("coverage_status") == "Included")
    booking_summary = included.groupBy("service", "customer_key").agg(
        F.min("customer").alias("customer"), F.count("*").alias("bookings_in_window"),
        F.countDistinct("svvd").alias("booking_voyages"),
        F.percentile_approx("days_from_cutoff", 0.5, 10000).alias("median_booking_day"))
    booking_summary = booking_summary.limit(100001).toPandas()
    booking_summary["median_booking_day"] = pd.to_numeric(booking_summary.median_booking_day, errors="coerce")
    if len(booking_summary) > 100000:
        bookings.unpersist()
        raise ValueError("Too many customer-service summaries. Set CUSTOMER or SERVICES and rerun.")
    audit_frame = spark.sql(extra_space_sql(YEAR, SERVICES, CUSTOMER)).cache()
    try:
        audit_coverage = audit_frame.groupBy("evidence_status").count().orderBy("evidence_status").toPandas()
        events = (audit_frame.filter(F.col("evidence_status") == "Positive requested-space edit")
                  .limit(MAX_AUDIT_ROWS + 1).toPandas())
    finally:
        audit_frame.unpersist()
    if len(events) > MAX_AUDIT_ROWS:
        bookings.unpersist()
        raise ValueError("Request history exceeds MAX_AUDIT_ROWS. Narrow CUSTOMER or SERVICES; no partial statistics were produced.")
    events = classify_event_times(events, AUDIT_TIMEZONE, as_of)
    events.loc[events.customer_key.isin(pooled) & (events.evidence_status == "Positive requested-space edit"),
               "evidence_status"] = "Pooled name; not an individual customer"
    print("\nRequested-space audit coverage")
    display(audit_coverage)
    print("\nPositive-edit timestamp and customer checks")
    display(events.groupby("evidence_status", dropna=False).size().reset_index(name="rows"))
    quantities = summarize_extra_space(events)
    names = pd.concat([booking_summary[["service", "customer_key", "customer"]],
                       quantities[["service", "customer_key", "customer"]]], ignore_index=True)
    names = names.sort_values("customer").drop_duplicates(["service", "customer_key"])
    summary = (names.merge(booking_summary.drop(columns="customer"), on=["service", "customer_key"], how="left", validate="one_to_one")
               .merge(quantities.drop(columns="customer"), on=["service", "customer_key"], how="left", validate="one_to_one"))
    if summary.empty:
        print("No usable customer records for these settings. Review the coverage tables above.")
        return {"booking_frame": bookings, "events": events, "summary": summary, "show_customer": None}
    for field in ("bookings_in_window", "booking_voyages", "recorded_increases", "plans"):
        summary[field] = summary[field].fillna(0).astype(int)
    print("\nCustomer summary — min / median / max are per recorded edit, in TEU")
    display(summary.sort_values(["service", "customer"]).round(2))
    print("Empty quantity statistics mean no qualifying evidence was found; they are not zero demand.")

    def show_customer(customer, service):
        key, service = clean_customer(customer), str(service).strip().upper()
        row = summary[(summary.customer_key == key) & (summary.service == service)]
        if row.empty:
            print("No usable records for that customer and service. Use a name from the summary table.")
            return
        selected_bookings = included.filter((F.col("customer_key") == key) & (F.col("service") == service))
        daily = selected_bookings.groupBy("day_from_cutoff").count().withColumnRenamed("count", "bookings").orderBy("day_from_cutoff").toPandas()
        selected_events = events[(events.customer_key == key) & (events.service == service) &
                                 (events.evidence_status == "Positive requested-space edit")].copy()
        selected_events = selected_events.sort_values(["recorded_clock", "audit_id"])
        name = row.iloc[0].customer
        with plt.rc_context({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white"}):
            plot_booking_and_space(daily, selected_events, name, service, DAYS_BEFORE, DAYS_AFTER)
        display(row.drop(columns="customer_key").round(2))
        print("\nExact requested-space edits")
        display(selected_events[["audit_id", "plan_id", "raw_event_time", "event_time_utc", "time_basis",
                                 "short_voyage", "agreement", "previous_requested_teu", "requested_total_teu",
                                 "extra_teu", "recorded_by"]])
        print("Voyage and agreement are populated only when consistent in available plan history.")
        print("\nDaily booking counts")
        display(daily)
        rows = selected_bookings.orderBy("booked_at_us", "shipment_num").limit(MAX_BOOKING_ROWS_SHOWN).toPandas()
        if not rows.empty:
            rows["booking_time_utc"] = pd.to_datetime(rows.booked_at_us.astype("int64"), unit="us", utc=True).astype(str)
            rows["cutoff_utc"] = pd.to_datetime(rows.cutoff_us.astype("int64"), unit="us", utc=True).astype(str)
            print(f"\nBooking timestamps — showing {len(rows):,} of {int(row.iloc[0].bookings_in_window):,} included bookings")
            display(rows[["shipment_num", "svvd", "loading_port", "booking_time_utc", "cutoff_utc", "days_from_cutoff"]])
        print("\nThis customer's booking coverage")
        display(bookings.filter((F.col("customer_key") == key) & (F.col("service") == service))
                .groupBy("coverage_status").count().orderBy("coverage_status"))

    available = summary.copy()
    if CHART_SERVICE:
        available = available[available.service == str(CHART_SERVICE).strip().upper()]
    if CUSTOMER:
        available = available[available.customer_key == clean_customer(CUSTOMER)]
    if available.empty:
        print("No usable records for CHART_SERVICE. Use the summary to choose another service.")
    else:
        available["both_sources"] = (available.bookings_in_window > 0) & (available.recorded_increases > 0)
        first = available.sort_values(["both_sources", "bookings_in_window", "recorded_increases", "customer_key"],
                                      ascending=[False, False, False, True]).iloc[0]
        print(f"\nShowing {first.customer} | {first.service}. All available customers remain in the summary.")
        show_customer(first.customer, first.service)
    print("\nTo switch customer: show_customer_activity('Customer name', 'SERVICE_CODE')")
    print("No source tables were changed. Each requestedTeu edit is counted once; other allocation stages are excluded.")
    return {"booking_frame": bookings, "events": events, "summary": summary, "show_customer": show_customer}


CUSTOMER_SPACE_RESULTS = run_booking_and_space()
show_customer_activity = CUSTOMER_SPACE_RESULTS["show_customer"]
