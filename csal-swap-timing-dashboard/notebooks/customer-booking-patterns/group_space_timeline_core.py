"""Customer groups, request timing and notebook execution. Bundled for copy/paste."""

def display_result_table(table, empty_message="No matching records."):
    """Do not send empty pandas results to Databricks' schema-inference display path."""
    if isinstance(table, pd.DataFrame) and table.empty:
        print(empty_message)
        if len(table.columns):
            print("Columns: " + ", ".join(str(column) for column in table.columns))
        return
    display(table)


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
    display_result_table(diagnostics)
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
        display_result_table(summary[columns].round(3))
        display_result_table(events, "No qualifying requested-space increases found for the selected customers.")
        display_result_table(bridge, "No request-plan cutoff evidence to display.")
        display_result_table(daily.merge(selected[["service", "customer_key", "customer", "timing_group"]],
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
        display_result_table(chosen[columns].round(3))
        print("Exact edit times, quantities and timing status — including unresolved edits")
        display_result_table(event_rows, "No qualifying requested-space increases found for this customer and service.")
        print("Exact daily booking counts")
        display_result_table(day_rows.sort_values("day_from_cutoff"))
    if SHOW_FIRST_CUSTOMER:
        first = summary.iloc[0]
        show_customer(first.customer, first.service)
    print("Switch the detail chart: show_group_customer('Customer name', 'SERVICE_CODE')")
    print("No source tables or compute settings were changed.")
    return {"summary": summary, "events": events, "plan_cutoffs": bridge, "daily": daily,
            "selected_profiles": selected, "all_profiles": profiles, "booking_frame": booking_frame,
            "settings": settings, "as_of": population_as_of, "show_customer": show_customer}
