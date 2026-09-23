# Databricks notebook source
# Paste this entire file into ONE Python cell in Databricks.
# All-service customer booking profiles, groups and two charts.
# Generated from 01_booking_timing.py and 02_customer_groups_and_charts.py.
try:
    import numpy
    import pandas
    import matplotlib
    import sklearn
except ImportError as exc:
    raise ImportError("This notebook needs numpy, pandas, matplotlib and scikit-learn on the selected compute.") from exc

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


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from pyspark.sql import functions as F


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


def describe_day(value):
    value = float(value)
    if abs(value) < 0.05:
        return "at cutoff"
    return f"{abs(value):.1f} days {'before' if value < 0 else 'after'}"


def customer_weighted_curves(daily, membership, days):
    """Zero-filled daily shares, averaged across customers in each timing group."""
    joined = daily.merge(membership[["customer_key", "service", "timing_group", "bookings"]],
                         on=["customer_key", "service"], how="inner", validate="many_to_one")
    joined["customer_daily_pct"] = 100.0 * joined["daily_bookings"] / joined["bookings"]
    observed = joined.groupby(["service", "customer_key"]).daily_bookings.sum()
    expected = membership.set_index(["service", "customer_key"]).bookings
    if not observed.reindex(expected.index, fill_value=0).eq(expected).all():
        raise ValueError("Daily counts do not reconcile to customer profiles. Rerun the combined cell.")
    sizes = membership.groupby("timing_group").size()
    output = []
    for group, size in sizes.items():
        rows = joined[joined.timing_group == group]
        counts = rows.groupby("day_from_cutoff").daily_bookings.sum().reindex(days, fill_value=0)
        shares = (rows.groupby("day_from_cutoff").customer_daily_pct.sum()
                  .reindex(days, fill_value=0) / size)
        for day in days:
            output.append({"timing_group": group, "day_from_cutoff": int(day),
                           "bookings": int(counts.loc[day]),
                           "mean_customer_booking_pct": float(shares.loc[day])})
    return pd.DataFrame(output)


def plot_customer_patterns(curves, profiles, service, days_before, days_after,
                          customer=None, max_customers=25):
    navy, red, grey = "#203D60", "#D20A2E", "#707B87"
    group_rows = profiles[profiles.timing_group != "Limited history"]
    ordered_groups = (group_rows[["timing_group", "group_order"]].drop_duplicates()
                      .sort_values("group_order").timing_group.tolist())
    if ordered_groups:
        fig, axes = plt.subplots(len(ordered_groups), 1,
                                 figsize=(12, max(3, 2.3 * len(ordered_groups))),
                                 sharex=True, squeeze=False)
        for ax, group in zip(axes.flat, ordered_groups):
            line = curves[curves.timing_group == group]
            members = group_rows[group_rows.timing_group == group]
            ax.plot(line.day_from_cutoff, line.mean_customer_booking_pct, color=navy, lw=1.8)
            ax.axvline(0, color=red, lw=1.2)
            label = "All eligible customers" if members.group_note.iloc[0].startswith("No clear") else group
            ax.set_title(f"{label}  ·  Usually {describe_day(members.median_day.median())}"
                         f"  ·  {len(members):,} customers / {int(members.bookings.sum()):,} bookings",
                         loc="left", fontsize=10, color=navy)
            ax.set_ylabel("Bookings (%)", fontsize=9)
            ax.set_ylim(bottom=0)
            ax.grid(axis="y", color="#E5E9EF", lw=0.6)
            ax.spines[["top", "right"]].set_visible(False)
        axes[-1, 0].set_xlabel("Days from TCR cutoff  |  0 = cutoff; negative = before")
        axes[-1, 0].set_xlim(-days_before, days_after)
        axes[-1, 0].xaxis.set_major_locator(MaxNLocator(integer=True, nbins=12))
        fig.suptitle(f"When customers usually book · {service}", x=0.09, ha="left",
                     fontsize=15, color=navy, fontweight="bold")
        fig.text(0.09, 0.012, "Each customer has equal weight. Daily bins begin at the cutoff time."
                 " Exact booking counts are in the daily table.", fontsize=9, color=grey)
        fig.tight_layout(rect=(0, 0.04, 1, 0.97))
        plt.show()
        plt.close(fig)
    shown = profiles.copy()
    if customer:
        key = " ".join(str(customer).split()).upper()
        shown = shown[shown.customer_key == key]
    else:
        shown = shown.sort_values(["bookings", "customer_key"], ascending=[False, True]).head(max_customers)
    shown = shown.sort_values(["median_day", "customer_key"])
    if shown.empty:
        print("No customer matches CHART_CUSTOMER in this service.")
        return
    fig, ax = plt.subplots(figsize=(12, max(4, 0.38 * len(shown) + 1.7)))
    for y, (_, row) in enumerate(shown.iterrows()):
        colour = grey if row.timing_group == "Limited history" else navy
        ax.plot([row.p25_day, row.p75_day], [y, y], color=colour, lw=4, solid_capstyle="round")
        ax.plot(row.median_day, y, "o", color=red, markersize=5)
    ax.axvline(0, color=red, lw=1, linestyle="--")
    labels = [f"{r.customer[:60]} · {r.timing_group} · n={int(r.bookings):,}"
              for r in shown.itertuples()]
    ax.set_yticks(np.arange(len(shown)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(-days_before, days_after)
    ax.set_xlabel("Days from TCR cutoff")
    ax.set_title(f"Customer booking windows · {service}", loc="left", color=navy,
                 fontsize=15, fontweight="bold", pad=20)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#E5E9EF", lw=0.6)
    fig.text(0.02, 0.012, "Dot = median. Line = middle 50% of bookings."
             " Grey = limited history. Full customer list is in the table.", color=grey, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    plt.show()
    plt.close(fig)


def build_customer_profiles():
    prepared = globals().get("CUSTOMER_TIMING")
    if not isinstance(prepared, dict) or prepared.get("frame") is None:
        raise RuntimeError("Run 01_booking_timing.py first, or run customer_booking_patterns_all_in_one.py.")
    settings = prepared["settings"]
    frame = prepared["frame"]
    included = frame.filter(F.col("coverage_status") == "Included")
    attributable = frame.filter(F.col("customer_key").isNotNull() & ~F.col("coverage_status").isin(
        "Booking time unresolved; year not assigned", "Conflicting current customer or route"))
    customer_coverage = attributable.groupBy("service", "customer_key").agg(
        F.min("customer").alias("customer"), F.count("*").alias("available_year_bookings"),
        F.sum(F.when(F.col("coverage_status") == "Included", 1).otherwise(0)).alias("included_bookings"))
    quantiles = F.percentile_approx("days_from_cutoff", [0.25, 0.5, 0.75], 10000)
    profile_frame = included.groupBy("service", "customer_key").agg(
        F.min("customer").alias("customer"), F.count("*").alias("bookings"),
        F.countDistinct("svvd").alias("voyages"), quantiles.alias("quantiles"),
        F.sum(F.when(F.col("days_from_cutoff") < 0, 1).otherwise(0)).alias("before_cutoff"),
        F.sum(F.when(F.col("days_from_cutoff") == 0, 1).otherwise(0)).alias("at_cutoff"),
        F.sum(F.when(F.col("days_from_cutoff") > 0, 1).otherwise(0)).alias("after_cutoff"),
        F.min("cutoff_us").alias("first_cutoff_us"), F.max("cutoff_us").alias("last_cutoff_us")
    ).join(customer_coverage.select("service", "customer_key", "available_year_bookings"),
           ["service", "customer_key"], "left")
    profiles = profile_frame.limit(100001).toPandas()
    if len(profiles) > 100000:
        raise RuntimeError("More than 100,000 customer-service profiles. Set SERVICES to a smaller list and rerun.")
    if profiles.empty:
        print("No bookings meet the comparison rules. See the coverage table; no groups or curves were fabricated.")
        return None
    profiles[["p25_day", "median_day", "p75_day"]] = pd.DataFrame(profiles.pop("quantiles").tolist(), index=profiles.index)
    profiles[["p25_day", "median_day", "p75_day"]] = profiles[["p25_day", "median_day", "p75_day"]].astype(float)
    profiles["middle_50pct_span_days"] = profiles.p75_day - profiles.p25_day
    profiles["after_cutoff_pct"] = 100.0 * profiles.after_cutoff / profiles.bookings
    profiles["profile_coverage_pct"] = 100.0 * profiles.bookings / profiles.available_year_bookings

    # Split by voyage cutoff, keeping every booking on the same voyage in one period.
    voyage_times = included.groupBy("service", "svvd").agg(F.min("cutoff_us").alias("voyage_cutoff_us"))
    splits = voyage_times.groupBy("service").agg(F.percentile_approx("voyage_cutoff_us", 0.5, 10000).alias("split_us"))
    period_rows = (included.join(voyage_times, ["service", "svvd"])
                   .join(splits, ["service"])
                   .withColumn("period", F.when(F.col("voyage_cutoff_us") < F.col("split_us"), "Earlier").otherwise("Later")))
    halves = period_rows.groupBy("service", "customer_key", "period").agg(
        F.count("*").alias("period_bookings"), F.countDistinct("svvd").alias("period_voyages"),
        F.percentile_approx("days_from_cutoff", 0.5, 10000).alias("period_median")
    ).toPandas()
    halves["period_median"] = halves.period_median.astype(float)
    for period, prefix in [("Earlier", "earlier"), ("Later", "later")]:
        part = halves[halves.period == period].drop(columns="period").rename(columns={
            "period_bookings": f"{prefix}_bookings", "period_voyages": f"{prefix}_voyages",
            "period_median": f"{prefix}_median_day"})
        profiles = profiles.merge(part, on=["service", "customer_key"], how="left", validate="one_to_one")
    profiles["median_shift_days"] = profiles.later_median_day - profiles.earlier_median_day
    enough = ((profiles.earlier_bookings >= 5) & (profiles.later_bookings >= 5) &
              (profiles.earlier_voyages >= 2) & (profiles.later_voyages >= 2))
    profiles["history_check"] = np.where(
        ~enough, "Not enough history in both periods",
        np.where(profiles.median_shift_days.abs() <= STABILITY_SHIFT_DAYS,
                 "Similar median across periods", "Median changed across periods"))
    profiles, model_summary = assign_timing_groups(
        profiles, MIN_BOOKINGS, MIN_VOYAGES, MIN_CUSTOMERS_PER_GROUP, MAX_GROUPS, MIN_SILHOUETTE)
    profiles["usual_booking_time"] = profiles.median_day.map(describe_day)
    profiles = profiles.sort_values(["service", "group_order", "median_day", "customer_key"]).reset_index(drop=True)
    groups = (profiles.groupby(["service", "timing_group", "group_order", "group_note"], dropna=False)
              .agg(customers=("customer_key", "size"), bookings=("bookings", "sum"),
                   median_customer_day=("median_day", "median"),
                   median_customer_span_days=("middle_50pct_span_days", "median"))
              .reset_index().sort_values(["service", "group_order"]))
    service_coverage = (frame.groupBy("service", "coverage_status").count().toPandas()
                        .pivot(index="service", columns="coverage_status", values="count").fillna(0))
    service_coverage["bookings_with_year_assigned"] = service_coverage.drop(
        columns=["Booking time unresolved; year not assigned"], errors="ignore").sum(axis=1)
    service_coverage["included_pct_of_year_bookings"] = np.where(
        service_coverage.bookings_with_year_assigned > 0,
        100.0 * service_coverage.get("Included", 0) / service_coverage.bookings_with_year_assigned,
        np.nan)
    print("\nCustomer booking patterns")
    print(f"{len(profiles):,} customer-service profiles | {int(profiles.bookings.sum()):,} bookings | "
          f"{profiles.service.nunique():,} services")
    print(f"Grouping minimum: {MIN_BOOKINGS} bookings across {MIN_VOYAGES} voyages per customer and service.")
    print("Customer names are matched by spacing and case only; different aliases remain separate.")
    print("These are observed booking habits, not a prediction that a customer will or will not book.")
    print("\nService coverage")
    display(service_coverage.reset_index())
    print("\nTiming groups — group numbers belong to each service")
    display(groups.drop(columns="group_order").round(2))
    print("\nCustomer lookup")
    customer_columns = ["service", "customer", "timing_group", "available_year_bookings", "bookings",
                        "profile_coverage_pct", "voyages",
                        "usual_booking_time", "p25_day", "median_day", "p75_day",
                        "before_cutoff", "at_cutoff", "after_cutoff", "after_cutoff_pct",
                        "history_check", "earlier_median_day", "later_median_day", "median_shift_days"]
    display(profiles[customer_columns].round(2))
    print("\nCustomers with no usable timing profile — see coverage reasons above")
    display(customer_coverage.filter(F.col("included_bookings") == 0)
            .select("service", "customer", "available_year_bookings", "included_bookings")
            .orderBy(F.desc("available_year_bookings"), "service", "customer"))
    print("\nGroup selection")
    display(model_summary.round(3))

    # All services are calculated. The selector controls only the two displayed figures.
    profiles["eligible_for_grouping"] = profiles.timing_group != "Limited history"
    service_sizes = (profiles.groupby("service").agg(eligible_customers=("eligible_for_grouping", "sum"),
                                                   customers=("customer_key", "size"), bookings=("bookings", "sum"))
                     .sort_values(["eligible_customers", "customers", "bookings"], ascending=False))
    selected = str(CHART_SERVICE).strip().upper() if CHART_SERVICE else service_sizes.index[0]

    def show_service(service, customer=None):
        service = str(service).strip().upper()
        members = profiles[profiles.service == service]
        if members.empty:
            print("No usable profiles for this service. Available: " + ", ".join(service_sizes.index))
            return None
        daily = (included.filter(F.col("service") == service)
                 .groupBy("service", "customer_key", "day_from_cutoff").count()
                 .withColumnRenamed("count", "daily_bookings").limit(2000001).toPandas())
        if len(daily) > 2000000:
            raise RuntimeError("More than 2 million customer-day rows in this service; narrow the population before plotting.")
        membership = members[members.timing_group != "Limited history"]
        days = list(range(-settings["days_before"], settings["days_after"]))
        if membership.empty:
            curves = pd.DataFrame(columns=["timing_group", "day_from_cutoff", "bookings", "mean_customer_booking_pct"])
            print("This service has limited customer history. Customer windows are shown without forced groups.")
        else:
            curves = customer_weighted_curves(daily, membership, days)
        with plt.rc_context({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white"}):
            plot_customer_patterns(curves, members, service, settings["days_before"],
                                   settings["days_after"], customer, MAX_CUSTOMERS_ON_CHART)
        print(f"Charts: {service}. All services remain in the customer and group tables above.")
        if not curves.empty:
            print("\nDaily group counts and customer-weighted curve values")
            display(curves.round({"mean_customer_booking_pct": 3}))
        print("\nExact daily booking counts by customer")
        names = members[["service", "customer_key", "customer", "timing_group"]]
        table = daily.merge(names, on=["service", "customer_key"], validate="many_to_one")
        if customer:
            table = table[table.customer_key == " ".join(str(customer).split()).upper()]
        display(table[["service", "customer", "timing_group", "day_from_cutoff", "daily_bookings"]]
                .sort_values(["customer", "day_from_cutoff"]))
        return curves

    curves = show_service(selected, CHART_CUSTOMER)
    print("\nChange the service with show_customer_service('SERVICE_CODE').")
    print("Use show_customer_service('SERVICE_CODE', 'Customer name') to focus the customer chart and daily table.")
    print("No source tables were changed. Groups describe the stated window and available matched bookings.")
    return {"profiles": profiles, "groups": groups, "model_summary": model_summary,
            "coverage": service_coverage, "curves": curves, "show_service": show_service}


CUSTOMER_RESULTS = build_customer_profiles()
if CUSTOMER_RESULTS is not None:
    show_customer_service = CUSTOMER_RESULTS["show_service"]
