# Databricks notebook source
# Paste this entire file into ONE Python cell. Run in the Windows VM.
# Existing CUSTOMER_RESULTS groups are reused. If absent, the same method rebuilds them.
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
import re
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from pyspark.sql import functions as F

TOP_CUSTOMERS = 25               # Distinct customers across all selected groups/services.
SELECT_SERVICES = None           # All available services; or ["PNW1", "PNW5"].
SELECT_CUSTOMERS = None          # Optional list of exact names; overrides top-25 selection.
AUDIT_TIMEZONE = "UTC"            # Confirmed by the user on 2026-09-23.
ROWS_PER_PAGE = 12
SHOW_FIRST_CUSTOMER = True
SHOW_TABLES = True
REBUILD_GROUPS = False           # True rebuilds; False preserves existing notebook groups.

# Used only when rebuilding the booking population and groups.
YEAR = 2026
SOURCE_SERVICES = None           # All services.
DAYS_BEFORE = 56
DAYS_AFTER = 14
MIN_BOOKINGS = 20
MIN_VOYAGES = 3
MIN_CUSTOMERS_PER_GROUP = 5
MAX_GROUPS = 8                    # Maximum to test; never forces three groups.
MIN_SILHOUETTE = 0.35
EXCLUDE_CUSTOMER_NAMES = ["Open Customers", "APN Unassigned"]

MAX_PROFILES = 100000
MAX_AUDIT_ROWS = 200000
MAX_DAILY_ROWS = 2000000



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


def assign_timing_groups(profiles, min_bookings=20, min_voyages=3,
                         min_group_size=5, max_groups=8, min_silhouette=0.35):
    """One equally weighted customer per service; volume is not a clustering feature."""
    result = profiles.copy()
    result["timing_group"] = "Limited history"
    result["group_note"] = "More bookings or voyages needed"
    result["group_order"] = 99
    if min_bookings < 1 or min_voyages < 1 or min_group_size < 2 or not 2 <= max_groups <= 20:
        raise ValueError("Check the grouping minimums and MAX_GROUPS (2–20).")
    if not 0 <= min_silhouette <= 1:
        raise ValueError("MIN_SILHOUETTE must be between 0 and 1.")
    diagnostics = []
    for service, service_rows in result.groupby("service", sort=True):
        eligible = service_rows[(service_rows.bookings >= min_bookings) &
                                (service_rows.voyages >= min_voyages)]
        if eligible.empty:
            diagnostics.append({"service": service, "customers_for_grouping": 0,
                                "groups": 0, "silhouette": None,
                                "decision": "Not enough customer history"})
            continue
        x = eligible[["p25_day", "median_day", "p75_day"]].to_numpy(dtype=float)
        candidates = []
        upper = min(max_groups, len(x) // min_group_size, len(np.unique(x, axis=0)))
        for k in range(2, upper + 1):
            labels = KMeans(n_clusters=k, n_init=10, max_iter=200,
                            random_state=42).fit_predict(x)
            _, sizes = np.unique(labels, return_counts=True)
            if len(sizes) != k or sizes.min() < min_group_size:
                continue
            # Keep each group represented if the silhouette calculation is sampled.
            if len(x) > 2000:
                rng = np.random.default_rng(42)
                seeds = np.concatenate([rng.choice(np.flatnonzero(labels == g), 2, replace=False)
                                        for g in range(k)])
                rest = np.setdiff1d(np.arange(len(x)), seeds)
                sample = np.concatenate([seeds, rng.choice(rest, 2000 - len(seeds), replace=False)])
            else:
                sample = np.arange(len(x))
            score = float(silhouette_score(x[sample], labels[sample]))
            candidates.append((k, score, labels))
        supported = [c for c in candidates if c[1] >= min_silhouette]
        if supported:
            best = max(c[1] for c in supported)
            k, score, labels = min((c for c in supported if c[1] >= best - 0.02),
                                   key=lambda c: c[0])
            note = "Exploratory timing group"
        else:
            k, score, labels = 1, None, np.zeros(len(x), dtype=int)
            note = "No clear separation into smaller groups"
        order = sorted(np.unique(labels), key=lambda g: float(np.median(x[labels == g, 1])))
        for position, raw_group in enumerate(order, 1):
            indexes = eligible.index[labels == raw_group]
            result.loc[indexes, "timing_group"] = f"G{position}"
            result.loc[indexes, "group_note"] = note
            result.loc[indexes, "group_order"] = position
        diagnostics.append({"service": service, "customers_for_grouping": len(x),
                            "groups": k, "silhouette": score,
                            "decision": note})
    return result, pd.DataFrame(diagnostics)


def _group_space_number(value):
    if pd.isna(value):
        return "—"
    number = float(value)
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.1f}"

def _group_space_range(row, prefix):
    return " / ".join(
        _group_space_number(row.get(f"{part}_{prefix}", np.nan))
        for part in ("min", "median", "max")
    )

def _group_space_style(ax):
    ax.set_facecolor("white")
    ax.spines[["top", "right"]].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D5DCE3")
    ax.tick_params(colors="#46566A", labelsize=9)
    ax.grid(axis="x", color="#E8EDF2", linewidth=0.7)
    ax.set_axisbelow(True)

def plot_group_space_overview(summary, before, after, rows_per_page=12):
    """Display separate booking and requested-space figures; return all figures.

    Ordering is all booking pages, then all requested-space pages. Customer rows
    have the same order in both sets. Quantity statistics use all qualifying
    increases; request timing uses only increases with usable cutoff timing.
    """
    if rows_per_page < 1 or before < 0 or after <= 0:
        raise ValueError("Use rows_per_page >= 1, before >= 0 and after > 0.")
    required = {"customer", "service", "timing_group", "bookings", "p25_day",
                "median_day", "p75_day", "request_timed_count", "request_count"}
    missing = required.difference(summary.columns)
    if missing:
        raise ValueError("Missing summary columns: " + ", ".join(sorted(missing)))
    navy, red = "#203D62", "#D10A2C"
    ordered = summary.copy()
    ordered["_group_order"] = pd.to_numeric(
        ordered["timing_group"].astype(str).str.extract(r"(\d+)", expand=False),
        errors="coerce",
    ).fillna(999)
    ordered = ordered.sort_values(
        ["service", "_group_order", "median_day", "bookings", "customer"],
        ascending=[True, True, True, False, True], kind="stable",
    )
    pages = max(1, int(np.ceil(len(ordered) / rows_per_page)))
    figures = []
    for kind in ("booking", "request"):
        is_request = kind == "request"
        title = "Requested-space timing and amounts" if is_request else "Customer booking timing"
        color, marker = (red, "D") if is_request else (navy, "o")
        for page_index in range(pages):
            page = ordered.iloc[page_index * rows_per_page:(page_index + 1) * rows_per_page]
            count = len(page)
            if not count:
                fig, ax = plt.subplots(figsize=(12, 3), facecolor="white")
                ax.axis("off")
                ax.set_title(title, loc="left", color=navy, fontweight="bold")
                ax.text(0.5, 0.5, "No customers meet the selected booking criteria.",
                        transform=ax.transAxes, ha="center", color="#687786", fontsize=11)
                plt.show()
                plt.close(fig)
                figures.append(fig)
                continue
            height = 0.82 * count + 3.2
            fig = plt.figure(figsize=(17, height), facecolor="white")
            widths = [3.5, 5.4, 3.5] if is_request else [3.5, 8.9]
            grid = fig.add_gridspec(1, len(widths), width_ratios=widths,
                                   left=0.025, right=0.985, bottom=1.05 / height,
                                   top=1 - 1.5 / height, wspace=0.04)
            labels_ax, ax = [fig.add_subplot(grid[0, n]) for n in range(2)]
            values_ax = fig.add_subplot(grid[0, 2]) if is_request else None
            for panel in fig.axes:
                panel.set_ylim(count - 0.5, -0.5)
            for panel in [labels_ax] + ([values_ax] if is_request else []):
                panel.set_xlim(0, 1)
                panel.axis("off")
            _group_space_style(ax)
            ax.spines["left"].set_visible(False)
            ax.set_yticks([])
            ax.set_xlim(-before, after)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.axvline(0, color="#687786", linewidth=1.2, linestyle="--", zorder=1)
            ax.set_xlabel("Days from TCR cutoff  ·  0 = cutoff", fontsize=10, color=navy, labelpad=10)
            labels_ax.set_title("Customer / service / group", loc="left", fontsize=10,
                                color=navy, fontweight="bold", pad=14)
            if is_request:
                values_ax.set_title("Added TEU; requested total TEU\nMin / median / max", loc="left",
                                    fontsize=10, color=navy, fontweight="bold", pad=14)
            for position, (_, row) in enumerate(page.iterrows()):
                name = textwrap.fill(str(row["customer"]), width=43, max_lines=3, placeholder="…")
                label = f"{name}\n{row['service']} · {row['timing_group']}"
                if not is_request:
                    label += f" · {_group_space_number(row['bookings'])} bookings"
                labels_ax.text(0, position, label, ha="left", va="center",
                               fontsize=9, color=navy, linespacing=1.35)
                if position % 2 == 0:
                    ax.axhspan(position - 0.48, position + 0.48, color="#F7F9FB", zorder=0)
                prefix = "request_" if is_request else ""
                quantiles = [row.get(f"{prefix}{part}_day", np.nan)
                             for part in ("p25", "median", "p75")]
                timed_count = row.get("request_timed_count", 0)
                enough = not is_request or (pd.notna(timed_count) and float(timed_count) > 0)
                if enough and all(pd.notna(value) for value in quantiles):
                    lower, middle, upper = map(float, quantiles)
                    ax.plot([lower, upper], [position, position], color=color, linewidth=3,
                            solid_capstyle="round", zorder=3)
                    ax.scatter([middle], [position], s=28, color=color, marker=marker, zorder=4)
                else:
                    message = "Request timing unavailable" if is_request else "Booking timing unavailable"
                    ax.text(0.02, position, message, transform=ax.get_yaxis_transform(),
                            fontsize=9, color="#687786", va="center")
                if is_request:
                    quantities = (
                        f"Added: {_group_space_range(row, 'extra_teu')}\n"
                        f"Total: {_group_space_range(row, 'requested_total_teu')}\n"
                        f"Timed / all increases: {_group_space_number(row['request_timed_count'])}"
                        f" / {_group_space_number(row['request_count'])}"
                    )
                    values_ax.text(0.03, position, quantities, fontsize=9, va="center",
                                   color=navy, linespacing=1.4)
            fig.suptitle(title, x=0.025, y=1 - 0.18 / height, ha="left", color=navy,
                         fontsize=16, fontweight="bold")
            legend = [Line2D([0], [0], color=color, marker=marker, linewidth=3,
                            label="Middle 50% and median of recorded increases" if is_request
                            else "Middle 50% and median of booking days")]
            fig.legend(handles=legend, loc="upper left", bbox_to_anchor=(0.022, 1 - 0.65 / height),
                       frameon=False, fontsize=10)
            fig.text(0.985, 1 - 0.32 / height, f"Page {page_index + 1} of {pages}",
                     ha="right", color="#687786", fontsize=9)
            note = (
                "Groups are defined within each service. Timing uses only increases with usable cutoff timing in the window; "
                "TEU statistics use all qualifying recorded increases.\n"
                "Request dates use current cutoff mappings, not reconstructed historical cutoffs. "
                "Requested-TEU edits do not establish that the customer submitted a request."
                if is_request else
                "Groups are defined within each service. Each marker is a customer/service median; the line covers the middle 50% of booking days.\n"
                "Timing uses only eligible bookings in the selected window and available route/cutoff records; historical route changes are not reconstructed."
            )
            fig.text(0.025, 0.17 / height, note, fontsize=8.5, color="#687786", linespacing=1.6)
            plt.show()
            plt.close(fig)
            figures.append(fig)
    return figures

def _group_space_detail_figure(customer, service, group, before, after, title):
    fig, ax = plt.subplots(figsize=(12, 5.4), facecolor="white")
    fig.subplots_adjust(top=0.69, bottom=0.25, left=0.095, right=0.97)
    fig.suptitle(textwrap.fill(str(customer), width=78), x=0.095, y=0.97,
                 ha="left", fontsize=15, fontweight="bold", color="#203D62")
    fig.text(0.095, 0.79, f"{service} · {group} · TCR cutoff = day 0", fontsize=10, color="#687786")
    _group_space_style(ax)
    ax.grid(axis="y", color="#EDF0F4", linewidth=0.7)
    ax.axvline(0, color="#687786", linestyle="--", linewidth=1.2)
    ax.set_xlim(-before, after)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title, loc="left", color="#203D62", fontweight="bold", fontsize=12, pad=14)
    ax.set_xlabel("Days from TCR cutoff  ·  negative = before  ·  positive = after",
                   color="#203D62", fontsize=10, labelpad=10)
    return fig, ax

def plot_group_space_customer(daily, events, customer, service, group, before, after):
    """Return two separately displayed figures: bookings, then requested space."""
    if before < 0 or after <= 0:
        raise ValueError("Use before >= 0 and after > 0.")
    navy, red = "#203D62", "#D10A2C"
    bookings = daily.copy()
    if not bookings.empty:
        bookings["day_from_cutoff"] = pd.to_numeric(bookings["day_from_cutoff"], errors="coerce")
        bookings["bookings"] = pd.to_numeric(bookings["bookings"], errors="coerce")
        bookings = bookings.loc[bookings["day_from_cutoff"].ge(-before)
                                & bookings["day_from_cutoff"].lt(after)].dropna(
                                    subset=["day_from_cutoff", "bookings"])
        bookings = bookings.groupby("day_from_cutoff", as_index=False)["bookings"].sum()
        if not bookings.empty:
            if not bookings["day_from_cutoff"].mod(1).eq(0).all():
                raise ValueError("Daily booking counts must use integer days from cutoff.")
            bookings = bookings.set_index("day_from_cutoff").reindex(
                pd.Index(range(-int(before), int(after)), name="day_from_cutoff"), fill_value=0,
            ).reset_index()
    requests = events.copy()
    if not requests.empty:
        requests["days_from_cutoff"] = pd.to_numeric(requests["days_from_cutoff"], errors="coerce")
        requests["extra_teu"] = pd.to_numeric(requests["extra_teu"], errors="coerce")
        requests = requests.loc[requests["days_from_cutoff"].ge(-before)
                                & requests["days_from_cutoff"].lt(after)
                                & requests["extra_teu"].gt(0)].dropna(
                                    subset=["days_from_cutoff", "extra_teu"])

    booking_fig, booking_ax = _group_space_detail_figure(
        customer, service, group, before, after, "When bookings are created")
    if bookings.empty:
        booking_ax.text(0.5, 0.5, "No usable booking records in this window.",
                        transform=booking_ax.transAxes, ha="center", color="#687786")
    else:
        booking_ax.plot(bookings["day_from_cutoff"], bookings["bookings"],
                        color=navy, linewidth=1.7, marker="o", markersize=2.5)
    booking_ax.set_ylabel("Bookings per day", color=navy, fontsize=10)
    booking_ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    booking_ax.set_ylim(0, max(1.0, float(bookings["bookings"].max()) * 1.15) if not bookings.empty else 1)
    booking_fig.text(0.095, 0.07,
                     "Daily counts use eligible bookings in the selected cutoff window.\n"
                     "Routes and cutoffs reflect available records; historical route changes are not reconstructed.",
                     color="#687786", fontsize=8.5, linespacing=1.6)
    plt.show()
    plt.close(booking_fig)

    request_fig, request_ax = _group_space_detail_figure(
        customer, service, group, before, after, "Recorded increases to requested space")
    if requests.empty:
        request_ax.text(0.5, 0.5, "No requested-space increases with usable cutoff timing.",
                        transform=request_ax.transAxes, ha="center", color="#687786")
    else:
        request_ax.vlines(requests["days_from_cutoff"], 0, requests["extra_teu"],
                          color=red, linewidth=0.8, alpha=0.35)
        request_ax.scatter(requests["days_from_cutoff"], requests["extra_teu"],
                           color=red, s=32, alpha=0.8, zorder=3)
        amount = requests["extra_teu"]
        stats = (f"{len(requests):,} timed increases · Added TEU: "
                 f"min {_group_space_number(amount.min())} / "
                 f"median {_group_space_number(amount.median())} / "
                 f"max {_group_space_number(amount.max())}")
        request_fig.text(0.095, 0.125, stats, color=navy, fontsize=9)
    request_ax.set_ylabel("Added TEU per recorded edit", color=navy, fontsize=10)
    request_ax.set_ylim(0, max(1.0, float(requests["extra_teu"].max()) * 1.15) if not requests.empty else 1)
    request_fig.text(0.095, 0.055,
                     "Each dot is one recorded increase; overlapping dots may hide multiple edits. "
                     "Requested-TEU edits do not establish customer submission.\n"
                     "Request timing uses current cutoff mappings, not reconstructed historical cutoffs.",
                     color="#687786", fontsize=8.5, linespacing=1.6)
    plt.show()
    plt.close(request_fig)
    return [booking_fig, request_fig]


def choose_group_customers(profiles, top_n=25, services=None, customer_names=None):
    required = {"service", "customer_key", "customer", "timing_group", "bookings",
                "p25_day", "median_day", "p75_day"}
    if not required.issubset(profiles.columns):
        raise ValueError("Customer profiles are missing: " + ", ".join(sorted(required - set(profiles.columns))))
    if profiles.duplicated(["service", "customer_key"]).any():
        raise ValueError("Customer profiles must contain one row per customer and service.")
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError("TOP_CUSTOMERS must be a positive integer.")
    rows = profiles[profiles.timing_group.fillna("").str.match(r"^G[0-9]+$")].copy()
    if services is not None:
        if isinstance(services, str) or not services:
            raise ValueError("SELECT_SERVICES must be None or a nonempty list.")
        rows = rows[rows.service.isin([str(s).strip().upper() for s in services])]
    if customer_names is not None:
        if isinstance(customer_names, str) or not customer_names:
            raise ValueError("SELECT_CUSTOMERS must be None or a nonempty list.")
        wanted = {clean_customer(x) for x in customer_names}
        missing = wanted - set(rows.customer_key)
        if missing:
            raise ValueError("No grouped history for: " + ", ".join(sorted(missing)))
        rows = rows[rows.customer_key.isin(wanted)]
    totals = (rows.groupby("customer_key", as_index=False).bookings.sum()
              .rename(columns={"bookings": "selected_customer_bookings"})
              .sort_values(["selected_customer_bookings", "customer_key"], ascending=[False, True]))
    if customer_names is None:
        totals = totals.head(top_n)
    totals["customer_rank"] = np.arange(1, len(totals) + 1)
    rows = rows.merge(totals, on="customer_key", validate="many_to_one")
    return rows.sort_values(["customer_rank", "service"]).reset_index(drop=True)

def plan_cutoff_sql(plans_view, booking_view):
    # Names are generated in this cell, never supplied as free-form SQL.
    for name in (plans_view, booking_view):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("Invalid temporary view name.")
    return f"""
WITH seed_shipments AS (
  SELECT DISTINCT UPPER(TRIM(CAST(a.shipment_num AS STRING))) AS shipment_num
  FROM datasources.csal.csal_booking_assoc_evt a
  INNER JOIN {plans_view} p ON CAST(a.csal_id AS STRING) = p.plan_id
  WHERE NULLIF(TRIM(CAST(a.shipment_num AS STRING)), '') IS NOT NULL
), assoc_raw AS (
  SELECT DISTINCT CAST(a.csal_id AS STRING) AS plan_id,
    UPPER(TRIM(CAST(a.shipment_num AS STRING))) AS shipment_num,
    REGEXP_REPLACE(NULLIF(UPPER(TRIM(a.service)), ''), '-[NSEW]$', '') AS service,
    a.match_ind,
    TRY_CAST(a.rec_upd_dt_utc AS TIMESTAMP) AS updated_at,
    TRY_CAST(a.rec_cre_dt_utc AS TIMESTAMP) AS created_at
  FROM datasources.csal.csal_booking_assoc_evt a
  INNER JOIN seed_shipments s ON UPPER(TRIM(CAST(a.shipment_num AS STRING))) = s.shipment_num
), ranked AS (
  SELECT *, DENSE_RANK() OVER (PARTITION BY plan_id, shipment_num
    ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST) AS revision
  FROM assoc_raw
), latest AS (
  SELECT *, COUNT(*) OVER (PARTITION BY plan_id, shipment_num) AS revision_rows
  FROM ranked WHERE revision = 1
), owners AS (
  SELECT shipment_num, COUNT(DISTINCT CASE WHEN match_ind = TRUE THEN plan_id END) AS matched_plans
  FROM latest GROUP BY shipment_num
), links AS (
  SELECT p.plan_id, a.shipment_num, b.svvd, b.loading_port, b.cutoff_us,
    CASE WHEN a.revision_rows = 1 AND a.match_ind = TRUE AND o.matched_plans = 1
      AND a.service = p.service AND b.service = p.service
      AND b.customer_key = p.customer_key
      AND b.coverage_status IN ('Included', 'Booked earlier than comparison window',
                               'Booked later than comparison window')
      AND p.short_voyage IS NOT NULL
      AND REGEXP_REPLACE(p.short_voyage, '[^A-Z0-9]', '') =
          CONCAT(SPLIT(b.svvd, '-')[1], SPLIT(SPLIT(b.svvd, '-')[2], ' ')[0])
      AND b.cutoff_us IS NOT NULL AND b.loading_port IS NOT NULL
      THEN 1 ELSE 0 END AS usable
  FROM {plans_view} p
  LEFT JOIN latest a ON p.plan_id = a.plan_id
  LEFT JOIN owners o ON a.shipment_num = o.shipment_num
  LEFT JOIN {booking_view} b ON a.shipment_num = b.shipment_num
), grouped AS (
  SELECT plan_id, COUNT(DISTINCT shipment_num) AS associated_shipments,
    SUM(CASE WHEN shipment_num IS NOT NULL AND usable = 0 THEN 1 ELSE 0 END) AS unresolved_link_rows,
    COUNT(DISTINCT CASE WHEN usable = 1 THEN
      TO_JSON(NAMED_STRUCT('voyage', svvd, 'port', loading_port, 'cutoff', cutoff_us)) END) AS route_cutoffs,
    MAX(CASE WHEN usable = 1 THEN cutoff_us END) AS candidate_cutoff_us,
    MAX(CASE WHEN usable = 1 THEN svvd END) AS candidate_svvd,
    MAX(CASE WHEN usable = 1 THEN loading_port END) AS candidate_loading_port
  FROM links GROUP BY plan_id
)
SELECT *,
  CASE WHEN associated_shipments = 0 THEN 'No available shipment association'
       WHEN unresolved_link_rows > 0 THEN 'Association or route context unresolved'
       WHEN route_cutoffs <> 1 THEN 'Several current routes or cutoffs'
       ELSE 'Unique current linked cutoff' END AS cutoff_status,
  CASE WHEN associated_shipments > 0 AND unresolved_link_rows = 0 AND route_cutoffs = 1
       THEN candidate_cutoff_us END AS cutoff_us
FROM grouped
"""

def assign_request_timing(events, plan_cutoffs, before, after, as_of):
    if plan_cutoffs.duplicated("plan_id").any():
        raise ValueError("The cutoff bridge must have one row per plan; requests must not multiply.")
    if events.audit_id.duplicated().any():
        raise ValueError("Request edits must have unique audit IDs.")
    result = events.merge(plan_cutoffs, on="plan_id", how="left", validate="many_to_one")
    result["days_from_cutoff"] = np.nan
    result["day_from_cutoff"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["timing_status"] = "Request edit excluded"
    end = pd.Timestamp(as_of)
    if end.tzinfo is None:
        raise ValueError("The read time must include its UTC offset.")
    for index, row in result.iterrows():
        if row.evidence_status != "Positive requested-space edit":
            result.at[index, "timing_status"] = row.evidence_status
            continue
        raw_time = row.event_time_utc
        try:
            instant = pd.Timestamp(raw_time) if pd.notna(raw_time) else pd.NaT
        except (ValueError, TypeError):
            instant = pd.NaT
        if pd.isna(instant) or instant.tzinfo is None:
            result.at[index, "timing_status"] = "Audit timezone or timestamp unresolved"
        elif instant > end:
            result.at[index, "timing_status"] = "Request time after read time"
        elif row.cutoff_status != "Unique current linked cutoff" or pd.isna(row.cutoff_us):
            result.at[index, "timing_status"] = (row.cutoff_status if pd.notna(row.cutoff_status)
                                                   else "No available shipment association")
        else:
            cutoff = pd.to_datetime(int(row.cutoff_us), unit="us", utc=True)
            days = (instant - cutoff).total_seconds() / 86400.0
            result.at[index, "days_from_cutoff"] = days
            result.at[index, "day_from_cutoff"] = int(np.floor(days))
            result.at[index, "timing_status"] = ("Included" if -before <= days < after
                                                 else "Outside comparison window")
    return result

def summarize_group_space(selected, events):
    valid = events[events.evidence_status == "Positive requested-space edit"]
    totals = summarize_extra_space(valid).drop(columns="customer")
    totals = totals.rename(columns={"recorded_increases": "request_count", "plans": "request_plans"})
    timed = valid[valid.timing_status == "Included"]
    timing = timed.groupby(["service", "customer_key"], as_index=False).agg(
        request_timed_count=("audit_id", "size"),
        request_p25_day=("days_from_cutoff", lambda x: x.quantile(0.25)),
        request_median_day=("days_from_cutoff", "median"),
        request_p75_day=("days_from_cutoff", lambda x: x.quantile(0.75)))
    result = selected.merge(totals, on=["service", "customer_key"], how="left", validate="one_to_one")
    result = result.merge(timing, on=["service", "customer_key"], how="left", validate="one_to_one")
    for col in ("request_count", "request_plans", "request_timed_count"):
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0).astype(int)
    result["request_timing_coverage_pct"] = np.where(result.request_count > 0,
        100.0 * result.request_timed_count / result.request_count, np.nan)
    return result

def get_group_population():
    saved = globals().get("CUSTOMER_RESULTS")
    prepared = globals().get("CUSTOMER_TIMING")
    if not REBUILD_GROUPS and isinstance(saved, dict) and isinstance(prepared, dict):
        if isinstance(saved.get("profiles"), pd.DataFrame) and prepared.get("frame") is not None:
            settings = prepared["settings"]
            print("Using the existing customer groups unchanged.")
            print(f"Existing population: year {settings['year']}; services {settings.get('services') or 'All'}.")
            return saved["profiles"].copy(), prepared["frame"], settings, prepared["as_of"]
    previous = globals().get("GROUP_SPACE_RESULTS")
    if not REBUILD_GROUPS and isinstance(previous, dict):
        if isinstance(previous.get("all_profiles"), pd.DataFrame) and previous.get("booking_frame") is not None:
            print("Reusing the customer groups from the previous run of this cell.")
            return previous["all_profiles"].copy(), previous["booking_frame"], previous["settings"], previous["as_of"]
    print("No prepared groups used. Building the same booking profiles and grouping method from source.")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frame = spark.sql(booking_timing_sql(YEAR, DAYS_BEFORE, DAYS_AFTER, end, SOURCE_SERVICES))
    names = [clean_customer(x) for x in EXCLUDE_CUSTOMER_NAMES]
    frame = frame.withColumn("coverage_status", F.when(
        (F.col("coverage_status") == "Included") & F.col("customer_key").isin(names),
        F.lit("Pooled allocation name; not an individual customer")).otherwise(F.col("coverage_status")))
    included = frame.filter(F.col("coverage_status") == "Included")
    profiles = included.groupBy("service", "customer_key").agg(
        F.min("customer").alias("customer"), F.count("*").alias("bookings"),
        F.countDistinct("svvd").alias("voyages"),
        F.percentile_approx("days_from_cutoff", [0.25, 0.5, 0.75], 10000).alias("quantiles")
    ).limit(MAX_PROFILES + 1).toPandas()
    if len(profiles) > MAX_PROFILES:
        raise ValueError("Too many customer profiles; narrow SOURCE_SERVICES. No partial groups were produced.")
    if profiles.empty:
        display(frame.groupBy("service", "coverage_status").count())
        raise ValueError("No usable booking profiles. Review the available route/cutoff coverage.")
    profiles[["p25_day", "median_day", "p75_day"]] = pd.DataFrame(profiles.pop("quantiles").tolist(), index=profiles.index)
    profiles[["p25_day", "median_day", "p75_day"]] = profiles[["p25_day", "median_day", "p75_day"]].astype(float)
    profiles, diagnostics = assign_timing_groups(profiles, MIN_BOOKINGS, MIN_VOYAGES,
        MIN_CUSTOMERS_PER_GROUP, MAX_GROUPS, MIN_SILHOUETTE)
    display(diagnostics)
    return profiles, frame, {"year": YEAR, "services": SOURCE_SERVICES,
        "days_before": DAYS_BEFORE, "days_after": DAYS_AFTER}, end

def run_group_space_timeline():
    if AUDIT_TIMEZONE:
        ZoneInfo(AUDIT_TIMEZONE)
    profiles, booking_frame, settings, population_as_of = get_group_population()
    selected = choose_group_customers(profiles, TOP_CUSTOMERS, SELECT_SERVICES, SELECT_CUSTOMERS)
    if selected.empty:
        raise ValueError("No grouped customers under these filters. Limited-history customers are not assigned invented groups.")
    if not isinstance(ROWS_PER_PAGE, int) or ROWS_PER_PAGE < 1:
        raise ValueError("ROWS_PER_PAGE must be a positive integer.")
    before, after, year = settings["days_before"], settings["days_after"], settings["year"]
    keys = spark.createDataFrame(list(selected[["service", "customer_key"]].itertuples(index=False, name=None)),
                                 "service string, customer_key string")
    included = booking_frame.filter(F.col("coverage_status") == "Included").join(keys, ["service", "customer_key"], "inner")
    daily = (included.groupBy("service", "customer_key", "day_from_cutoff").count()
             .withColumnRenamed("count", "bookings").limit(MAX_DAILY_ROWS + 1).toPandas())
    if len(daily) > MAX_DAILY_ROWS:
        raise ValueError("Too many daily rows; reduce TOP_CUSTOMERS or SELECT_SERVICES.")
    actual = daily.groupby(["service", "customer_key"]).bookings.sum()
    expected = selected.set_index(["service", "customer_key"]).bookings
    if not actual.reindex(expected.index, fill_value=0).eq(expected).all():
        raise ValueError("The source counts changed since grouping. Set REBUILD_GROUPS=True and rerun to keep the charts consistent.")
    read_time = datetime.now(timezone.utc)
    audit = spark.sql(extra_space_sql(year, selected.service.unique().tolist())).join(keys,
                                       ["service", "customer_key"], "inner")
    screening = audit.groupBy("evidence_status").count().orderBy("evidence_status").toPandas()
    events = audit.filter(F.col("evidence_status") == "Positive requested-space edit").limit(MAX_AUDIT_ROWS + 1).toPandas()
    if len(events) > MAX_AUDIT_ROWS:
        raise ValueError("Too many request edits; narrow the customer or service selection. No sample statistics were produced.")
    events = classify_event_times(events, AUDIT_TIMEZONE, read_time)
    if events.empty:
        bridge = pd.DataFrame(columns=["plan_id", "cutoff_us", "cutoff_status"])
    else:
        plans = events[["plan_id", "customer_key", "service", "short_voyage"]].drop_duplicates()
        if plans.plan_id.duplicated().any():
            raise ValueError("A request plan has conflicting customer, service or voyage context.")
        plan_rows = [tuple(None if pd.isna(v) else str(v) for v in row)
                     for row in plans.itertuples(index=False, name=None)]
        prefix = "group_space_" + uuid4().hex[:10]
        pv, bv = prefix + "_plans", prefix + "_bookings"
        try:
            spark.createDataFrame(plan_rows, "plan_id string, customer_key string, service string, short_voyage string").createOrReplaceTempView(pv)
            booking_frame.createOrReplaceTempView(bv)
            bridge = spark.sql(plan_cutoff_sql(pv, bv)).toPandas()
        finally:
            spark.catalog.dropTempView(pv)
            spark.catalog.dropTempView(bv)
    events = assign_request_timing(events, bridge, before, after, read_time)
    summary = summarize_group_space(selected, events)
    print(f"{selected.customer_key.nunique()} customers | {len(selected)} customer/service profiles | {year}")
    print(f"Booking population read: {population_as_of}. Request/association read started: {read_time.isoformat()}.")
    print(f"Window: −{before} to +{after} days (upper endpoint excluded). Audit timezone: {AUDIT_TIMEZONE or 'Unconfirmed'}.")
    print("Groups are preserved within each service. G1 is earliest; the number of groups depends on that service.")
    print("Booking time uses the confirmed original booking field. Request time uses direct positive requestedTeu edits.")
    print("Request cutoffs use complete, unambiguous current shipment links; they are not historical schedule snapshots.")
    with plt.rc_context({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white"}):
        plot_group_space_overview(summary, before, after, ROWS_PER_PAGE)
    print("\nBEGIN CUSTOMER TIMELINE RESULTS")
    columns = ["customer", "service", "timing_group", "bookings", "p25_day", "median_day", "p75_day",
               "request_count", "request_timed_count", "request_timing_coverage_pct", "request_median_day",
               "min_extra_teu", "median_extra_teu", "max_extra_teu",
               "min_requested_total_teu", "median_requested_total_teu", "max_requested_total_teu"]
    print(summary[columns].round(3).to_csv(index=False, sep="\t"))
    print("Request screening (selected customer/service contexts only)")
    print(screening.to_csv(index=False, sep="\t"))
    print("Request timing coverage")
    print(events.groupby("timing_status", dropna=False).size().rename("edits").reset_index().to_csv(index=False, sep="\t"))
    print("END CUSTOMER TIMELINE RESULTS")
    print("TEU statistics use all qualifying increases in the recorded year; timing uses only the mapped, in-window subset.")
    print("Missing request timing or quantity is not zero demand. Names are matched by case and spacing, not by fuzzy matching.")
    if SHOW_TABLES:
        display(summary[columns].round(3))
        display(events)
        display(bridge)
        display(daily.merge(selected[["service", "customer_key", "customer", "timing_group"]],
                            on=["service", "customer_key"], validate="many_to_one"))

    def show_customer(customer, service):
        key, svc = clean_customer(customer), str(service).strip().upper()
        chosen = summary[(summary.customer_key == key) & (summary.service == svc)]
        if chosen.empty:
            print("This customer/service is outside the selected list. Set SELECT_CUSTOMERS and rerun to include it.")
            return
        row = chosen.iloc[0]
        day_rows = daily[(daily.customer_key == key) & (daily.service == svc)]
        event_rows = events[(events.customer_key == key) & (events.service == svc)]
        with plt.rc_context({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white"}):
            plot_group_space_customer(day_rows, event_rows[event_rows.timing_status == "Included"],
                                      row.customer, svc, row.timing_group, before, after)
        display(chosen[columns].round(3))
        print("Exact edit times, quantities and timing status — including unresolved edits")
        display(event_rows)
        print("Exact daily booking counts")
        display(day_rows.sort_values("day_from_cutoff"))
    if SHOW_FIRST_CUSTOMER:
        first = summary.iloc[0]
        show_customer(first.customer, first.service)
    print("Switch the detail chart: show_group_customer('Customer name', 'SERVICE_CODE')")
    print("No source tables or compute settings were changed.")
    return {"summary": summary, "events": events, "plan_cutoffs": bridge, "daily": daily,
            "selected_profiles": selected, "all_profiles": profiles, "booking_frame": booking_frame,
            "settings": settings, "as_of": population_as_of, "show_customer": show_customer}


GROUP_SPACE_RESULTS = run_group_space_timeline()
show_group_customer = GROUP_SPACE_RESULTS["show_customer"]
