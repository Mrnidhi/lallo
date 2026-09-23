%python
from datetime import datetime, timezone, date
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

SERVICE = None  # All services. Enter a service code to filter.
DETAIL_FROM = "2026-05-01"
CUTOFF_FROM = "2026-06-01"
CHANGES_FROM = "2026-06-01"

for value in (DETAIL_FROM, CUTOFF_FROM, CHANGES_FROM):
    date.fromisoformat(value)
as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
service_filter = "1 = 1"
if SERVICE:
    service_filter = "service = '" + SERVICE.strip().upper().replace("'", "''") + "'"

timing_sql = f"""
WITH params AS (
  SELECT TIMESTAMP '{as_of}' AS as_of_utc,
         CAST('{DETAIL_FROM}T00:00:00Z' AS TIMESTAMP) AS first_detail_utc,
         CAST('{CUTOFF_FROM}T00:00:00Z' AS TIMESTAMP) AS first_cutoff_utc
),
detail_raw AS (
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
               AND SUBSTRING(corp_direction, 1, 1) IN ('N', 'S', 'E', 'W')
      THEN CONCAT(REGEXP_REPLACE(service, '-[NSEW]$', ''), '-',
                  corp_vessel, '-',
                  CASE WHEN LENGTH(corp_voyage) < 3
                    THEN LPAD(corp_voyage, 3, '0') ELSE corp_voyage END,
                  ' ', SUBSTRING(corp_direction, 1, 1)) END AS corp_svvd,
    CASE WHEN first_service IS NOT NULL AND first_vessel IS NOT NULL
               AND first_voyage IS NOT NULL
               AND SUBSTRING(first_direction, 1, 1) IN ('N', 'S', 'E', 'W')
      THEN CONCAT(REGEXP_REPLACE(first_service, '-[NSEW]$', ''), '-',
                  first_vessel, '-',
                  CASE WHEN LENGTH(first_voyage) < 3
                    THEN LPAD(first_voyage, 3, '0') ELSE first_voyage END,
                  ' ', SUBSTRING(first_direction, 1, 1)) END AS first_svvd
  FROM detail_raw
),
detail_ranked AS (
  SELECT *, DENSE_RANK() OVER (
    PARTITION BY shipment_num ORDER BY detail_updated_at DESC NULLS LAST
  ) AS current_rank
  FROM detail_routes
  WHERE shipment_num IS NOT NULL
),
detail_one AS (
  SELECT shipment_num,
    MAX(service) AS service,
    MAX(corp_svvd) AS corp_svvd,
    MAX(first_svvd) AS first_svvd,
    MAX(loading_port) AS loading_port,
    MAX(first_port) AS first_port,
    MIN(detail_record_created_at) AS detail_record_created_at,
    COUNT(DISTINCT detail_record_created_at) AS detail_creation_values,
    SUM(CASE WHEN detail_record_created_at IS NULL THEN 1 ELSE 0 END)
      AS detail_missing_creation_rows,
    COUNT(DISTINCT CONCAT_WS('||',
      COALESCE(service, '<null>'), COALESCE(corp_svvd, '<null>'),
      COALESCE(first_svvd, '<null>'), COALESCE(loading_port, '<null>'),
      COALESCE(first_port, '<null>'), COALESCE(detail_sail_week, '<null>')
    )) AS current_route_variants
  FROM detail_ranked
  WHERE current_rank = 1
  GROUP BY shipment_num
),
shipment_one AS (
  SELECT NULLIF(UPPER(TRIM(CAST(shipment_number AS STRING))), '') AS shipment_num,
    MIN(TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS record_created_at,
    COUNT(DISTINCT TRY_CAST(rec_cre_dt_utc AS TIMESTAMP)) AS distinct_creation_times,
    SUM(CASE WHEN TRY_CAST(rec_cre_dt_utc AS TIMESTAMP) IS NULL THEN 1 ELSE 0 END) AS missing_creation_rows
  FROM datasources.csal.csal_shipment
  WHERE shipment_number IS NOT NULL
  GROUP BY NULLIF(UPPER(TRIM(CAST(shipment_number AS STRING))), '')
),
stop_raw AS (
  SELECT CAST(id AS STRING) AS stop_id,
    COALESCE(NULLIF(UPPER(TRIM(CAST(msg_business_key AS STRING))), ''),
             CONCAT('ID:', CAST(id AS STRING))) AS stop_identity,
    NULLIF(UPPER(TRIM(CAST(port_code AS STRING))), '') AS stop_port,
    CASE WHEN use_dep_svvd = TRUE
           THEN NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST(dep_svvd AS STRING))), ' +', ' '), '')
         WHEN use_dep_svvd = FALSE
           THEN NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST(arr_svvd AS STRING))), ' +', ' '), '')
    END AS effective_svvd,
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
  ) AS current_rank
  FROM stop_raw
),
stop_current AS (
  SELECT *, COUNT(*) OVER (PARTITION BY stop_identity) AS current_stop_rows
  FROM stop_ranked
  WHERE current_rank = 1
),
matched AS (
  SELECT d.shipment_num, d.service, d.corp_svvd, d.first_svvd,
    d.loading_port, d.first_port, d.current_route_variants,
    d.detail_record_created_at, d.detail_creation_values, d.detail_missing_creation_rows,
    sh.record_created_at, sh.distinct_creation_times, sh.missing_creation_rows,
    COUNT(DISTINCT s.stop_identity) AS exact_stops,
    COUNT(DISTINCT s.stop_id) AS exact_stop_rows,
    MAX(s.current_stop_rows) AS max_stop_revision_rows,
    COUNT(DISTINCT s.cutoff_ts) AS distinct_cutoffs,
    MAX(s.cutoff_ts) AS cutoff_ts,
    MAX(CASE WHEN s.stop_identity IS NOT NULL AND s.stop_flags_ok = 0
      THEN 1 ELSE 0 END) AS flagged_stop
  FROM detail_one d
  LEFT JOIN shipment_one sh ON sh.shipment_num = d.shipment_num
  LEFT JOIN stop_current s ON s.effective_svvd = d.corp_svvd
                          AND s.stop_port = d.loading_port
  GROUP BY d.shipment_num, d.service, d.corp_svvd, d.first_svvd,
    d.loading_port, d.first_port, d.current_route_variants,
    d.detail_record_created_at, d.detail_creation_values, d.detail_missing_creation_rows,
    sh.record_created_at, sh.distinct_creation_times, sh.missing_creation_rows
),
scoped AS (
  SELECT m.*, p.as_of_utc, p.first_cutoff_utc,
    CAST(FLOOR((UNIX_MICROS(m.record_created_at) - UNIX_MICROS(m.cutoff_ts))
               / 86400000000.0) AS INT) AS day_from_cutoff
  FROM matched m CROSS JOIN params p
  WHERE m.detail_record_created_at BETWEEN p.first_detail_utc AND p.as_of_utc
     OR m.detail_record_created_at IS NULL
),
classified AS (
  SELECT *,
    CASE
      WHEN current_route_variants <> 1 OR detail_creation_values <> 1
        OR detail_missing_creation_rows > 0 THEN 'ROUTE_OR_DETAIL_TIME_UNRESOLVED'
      WHEN corp_svvd IS NULL OR first_svvd IS NULL
        OR loading_port IS NULL OR first_port IS NULL THEN 'MISSING_ROUTE_FIELDS'
      WHEN first_svvd <> corp_svvd OR first_port <> loading_port
        THEN 'OUTSIDE_SAME_LEG_SCOPE'
      WHEN record_created_at IS NULL OR distinct_creation_times <> 1
        OR missing_creation_rows <> 0 OR record_created_at > as_of_utc
        THEN 'SHIPMENT_CREATION_UNRESOLVED'
      WHEN exact_stops = 0 THEN 'NO_EXACT_STOP'
      WHEN exact_stops <> 1 OR exact_stop_rows <> 1
        OR max_stop_revision_rows <> 1 THEN 'AMBIGUOUS_STOP'
      WHEN flagged_stop <> 0 THEN 'STOP_FLAGS_REQUIRE_REVIEW'
      WHEN distinct_cutoffs <> 1 OR cutoff_ts IS NULL THEN 'CUTOFF_UNRESOLVED'
      WHEN cutoff_ts < first_cutoff_utc THEN 'CUTOFF_BEFORE_SELECTED_START'
      WHEN cutoff_ts > as_of_utc - INTERVAL 14 DAYS THEN 'INSUFFICIENT_FOLLOWUP'
      WHEN day_from_cutoff NOT BETWEEN -28 AND 13 THEN 'OUTSIDE_DISPLAY_WINDOW'
      ELSE 'IN_WINDOW'
    END AS result_status
  FROM scoped
)
SELECT day_from_cutoff, COUNT(*) AS records
FROM classified
WHERE result_status = 'IN_WINDOW' AND {service_filter}
GROUP BY day_from_cutoff
ORDER BY day_from_cutoff
"""

allocation_sql = f"""
WITH params AS (
  SELECT DATE '{CHANGES_FROM}' AS first_recorded_date,
         DATE '{as_of[:10]}' AS last_recorded_date
),
raw_distinct AS (
  SELECT DISTINCT
    id AS change_log_id, csal_id AS plan_id,
    NULLIF(UPPER(TRIM(service)), '') AS service,
    customer, agreement, tcr, week_num, vessel_voyage,
    TRIM(updated_on) AS raw_update_time,
    updated_by, deleted,
    LOWER(TRIM(status)) AS plan_status,
    LOWER(TRIM(acceptance_status)) AS approval_status,
    TRY_CAST(last_reviewed_teu AS DECIMAL(18,6)) AS previous_reviewed_teu,
    TRY_CAST(reviewed_teu AS DECIMAL(18,6)) AS current_reviewed_teu
  FROM datasources.csal.csal_change_log
),
identified AS (
  SELECT *, COUNT(*) OVER (PARTITION BY change_log_id) AS versions_of_id,
    CASE WHEN raw_update_time RLIKE '^[0-9]{{14}}([.][0-9]{{1,9}})?$'
      THEN TRY_CAST(CONCAT(SUBSTRING(raw_update_time, 1, 4), '-',
                           SUBSTRING(raw_update_time, 5, 2), '-',
                           SUBSTRING(raw_update_time, 7, 2)) AS DATE)
    END AS recorded_date
  FROM raw_distinct
),
scoped AS (
  SELECT i.*,
    current_reviewed_teu - previous_reviewed_teu AS recorded_teu_difference
  FROM identified i CROSS JOIN params p
  WHERE plan_status = 'finalized'
    AND recorded_date BETWEEN p.first_recorded_date AND p.last_recorded_date
),
classified AS (
  SELECT *, CASE
    WHEN change_log_id IS NULL OR plan_id IS NULL OR versions_of_id <> 1
      THEN 'ID_UNRESOLVED'
    WHEN deleted IS NULL OR deleted = TRUE
      OR approval_status IS NULL OR approval_status <> 'tcc accepted'
      THEN 'DELETION_OR_APPROVAL_UNRESOLVED'
    WHEN previous_reviewed_teu IS NULL OR current_reviewed_teu IS NULL
      THEN 'PREVIOUS_OR_CURRENT_VALUE_MISSING'
    WHEN previous_reviewed_teu < 0 OR current_reviewed_teu < 0
      THEN 'NEGATIVE_ALLOCATION_REQUIRES_REVIEW'
    WHEN recorded_teu_difference > 0 THEN 'INCREASE'
    WHEN recorded_teu_difference < 0 THEN 'DECREASE'
    ELSE 'UNCHANGED'
  END AS revision_kind
  FROM scoped
)
SELECT DATE_FORMAT(recorded_date, 'EEE') AS weekday,
  SUM(CASE WHEN revision_kind = 'INCREASE'
    THEN recorded_teu_difference ELSE 0 END) AS increase_teu,
  SUM(CASE WHEN revision_kind = 'DECREASE'
    THEN -recorded_teu_difference ELSE 0 END) AS decrease_teu
FROM classified
WHERE revision_kind IN ('INCREASE', 'DECREASE', 'UNCHANGED')
  AND {service_filter}
GROUP BY DATE_FORMAT(recorded_date, 'EEE')
"""

daily_rows = spark.sql(timing_sql).collect()
allocation_rows = spark.sql(allocation_sql).collect()

daily = {int(r["day_from_cutoff"]): int(r["records"]) for r in daily_rows}
days = list(range(-28, 14))
counts = [daily.get(day, 0) for day in days]
total = sum(counts)
cumulative = [0.0]
running = 0
for count in counts:
    running += count
    cumulative.append(100.0 * running / total if total else 0.0)

weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
allocation = {r["weekday"]: r for r in allocation_rows}
increases = [float(allocation[d]["increase_teu"] or 0) if d in allocation else 0
             for d in weekdays]
decreases = [float(allocation[d]["decrease_teu"] or 0) if d in allocation else 0
             for d in weekdays]

blue, red = "#203C60", "#D00B2E"
with plt.rc_context({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": "white",
                     "axes.facecolor": "white", "text.color": "#222222",
                     "axes.labelcolor": "#222222", "xtick.color": "#222222",
                     "ytick.color": "#222222"}):
    fig = plt.figure(figsize=(14, 9))
    grid = fig.add_gridspec(2, 2, hspace=0.55, wspace=0.25)
    daily_ax = fig.add_subplot(grid[0, 0])
    cumulative_ax = fig.add_subplot(grid[0, 1])
    allocation_ax = fig.add_subplot(grid[1, :])

    for ax in (daily_ax, cumulative_ax, allocation_ax):
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)

    if total:
        daily_ax.plot(days, counts, color=blue, linewidth=2)
        cumulative_ax.step([-28] + [d + 1 for d in days], cumulative,
                           where="post", color=blue, linewidth=2)
        before_share = cumulative[28]
        cumulative_ax.scatter([0], [before_share], color=red, zorder=3)
        cumulative_ax.annotate(f"{before_share:.1f}% before cutoff",
                              (0, before_share), xytext=(8, -16),
                              textcoords="offset points", fontsize=9)
    else:
        for ax in (daily_ax, cumulative_ax):
            ax.text(0.5, 0.5, "No qualifying timing records",
                    ha="center", va="center", transform=ax.transAxes)

    daily_ax.set(title=f"Daily shipment records · n = {total:,}",
                 xlabel="Days from TCR cutoff", ylabel="Records created")
    daily_ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    cumulative_ax.set(title="Cumulative share within the window",
                      xlabel="Days from TCR cutoff", ylabel="Records accumulated (%)",
                      ylim=(0, 105))
    for ax in (daily_ax, cumulative_ax):
        ax.axvline(0, color=red, linestyle="--", linewidth=1)
        ax.set_xlim(-28, 14)
        ax.set_xticks([-28, -21, -14, -7, 0, 7, 14])
    daily_ax.set_ylim(bottom=0)

    if allocation_rows:
        positions = list(range(7))
        allocation_ax.bar([x - 0.2 for x in positions], increases,
                          width=0.4, color=blue, label="Increase")
        allocation_ax.bar([x + 0.2 for x in positions], decreases,
                          width=0.4, color=red, label="Decrease")
        allocation_ax.legend(frameon=False)
    else:
        allocation_ax.text(0.5, 0.5, "No comparable allocation records",
                           ha="center", va="center", transform=allocation_ax.transAxes)
    allocation_ax.set(title="Allocation revisions by recorded weekday",
                      xlabel="Finalization weekday", ylabel="Recorded TEU differences",
                      xticks=list(range(7)), xticklabels=weekdays, ylim=(0, None))
    allocation_ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    fig.suptitle(SERVICE.strip().upper() if SERVICE else "All services", fontsize=14)
    fig.subplots_adjust(bottom=0.14, top=0.91)
    fig.text(0.08, 0.065,
             "Timing: eligible direct routes; latest cutoffs with 14 days of follow-up. "
             "Record creation is not confirmed booking time.", fontsize=9)
    fig.text(0.08, 0.043,
             "Allocation: recorded finalization dates; timezone unconfirmed. "
             "Revisions are not confirmed swaps; weekday totals are not adjusted for weekday exposure.", fontsize=9)
    plt.show()
    plt.close(fig)
