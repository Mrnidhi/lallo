from uuid import uuid4

# Run as one Python cell in Databricks. Source tables are only read.
START_DATE = "2026-06-01"
START_DAY = START_DATE.replace("-", "")
tag = "swap_timing_" + uuid4().hex[:8]

def make_view(suffix, sql):
    name = tag + "_" + suffix
    spark.sql(sql).createOrReplaceTempView(name)
    return name

def show(title, sql):
    print("\n" + title)
    display(spark.sql(sql))

# These are rows currently marked finalized with a recorded value change.
# The raw update timestamp is not necessarily the finalization time.
# A balanced pair is only a candidate:
# two opposite changes on one service, plan week, short voyage, and raw update time.
changes = make_view("changes", f"""
SELECT
  CAST(id AS STRING) AS change_id,
  CAST(csal_id AS STRING) AS csal_id,
  UPPER(TRIM(service)) AS service,
  UPPER(TRIM(week_num)) AS plan_week,
  UPPER(TRIM(vessel_voyage)) AS short_voyage,
  UPPER(TRIM(customer)) AS customer,
  UPPER(TRIM(agreement)) AS agreement,
  UPPER(TRIM(tcr)) AS tcr,
  updated_on AS raw_update_time,
  CAST(TRY_TO_TIMESTAMP(CAST(updated_on AS STRING),
                        'yyyyMMddHHmmss.SSS') AS DATE) AS raw_update_date,
  TRY_CAST(reviewed_teu AS DECIMAL(18,3))
    - TRY_CAST(last_reviewed_teu AS DECIMAL(18,3)) AS delta_teu
FROM datasources.csal.csal_change_log
WHERE COALESCE(deleted, FALSE) = FALSE
  AND UPPER(TRIM(status)) = 'FINALIZED'
  AND UPPER(TRIM(acceptance_status)) = 'TCC ACCEPTED'
  AND last_reviewed_teu IS NOT NULL
  AND reviewed_teu IS NOT NULL
  AND updated_on RLIKE '^[0-9]{{14}}[.][0-9]{{3}}$'
  AND SUBSTR(updated_on, 1, 8) >= '{START_DAY}'
  AND TRY_TO_TIMESTAMP(CAST(updated_on AS STRING),
                       'yyyyMMddHHmmss.SSS') IS NOT NULL
  AND NULLIF(TRIM(service), '') IS NOT NULL
  AND NULLIF(TRIM(week_num), '') IS NOT NULL
  AND NULLIF(TRIM(vessel_voyage), '') IS NOT NULL
""")

groups = make_view("groups", f"""
SELECT
  SHA2(CONCAT_WS('|', service, plan_week, short_voyage,
                 raw_update_time), 256) AS pair_key,
  service, plan_week, short_voyage, raw_update_time,
  MAX(raw_update_date) AS raw_update_date,
  COUNT(*) AS revision_rows,
  COUNT(DISTINCT csal_id) AS plans,
  SUM(CASE WHEN delta_teu > 0 THEN 1 ELSE 0 END) AS increase_rows,
  SUM(CASE WHEN delta_teu < 0 THEN 1 ELSE 0 END) AS decrease_rows,
  SUM(delta_teu) AS net_delta_teu,
  SUM(CASE WHEN delta_teu > 0 THEN delta_teu ELSE 0 END)
    AS gross_increase_teu
FROM {changes}
WHERE delta_teu <> 0
GROUP BY service, plan_week, short_voyage, raw_update_time
""")

pairs = make_view("pairs", f"""
SELECT
  g.pair_key, c.change_id, c.csal_id,
  c.service, c.plan_week, c.short_voyage,
  c.customer, c.agreement, c.tcr,
  c.raw_update_time, c.raw_update_date, c.delta_teu,
  CASE WHEN c.delta_teu > 0 THEN 'INCREASE' ELSE 'DECREASE' END AS side,
  g.gross_increase_teu AS candidate_teu
FROM {groups} g
JOIN {changes} c
  ON g.service = c.service
 AND g.plan_week = c.plan_week
 AND g.short_voyage = c.short_voyage
 AND g.raw_update_time = c.raw_update_time
 AND c.delta_teu <> 0
WHERE g.revision_rows = 2
  AND g.plans = 2
  AND g.increase_rows = 1
  AND g.decrease_rows = 1
  AND g.net_delta_teu = 0
""")

# An audit change must agree with the exact finalized revision and its TEU delta.
audit_side = make_view("audit_side", f"""
SELECT
  p.pair_key, p.csal_id, p.side,
  COUNT(DISTINCT CASE
    WHEN LOWER(a.type) = 'finalize'
     AND LOWER(REGEXP_REPLACE(a.change_field, '[^A-Za-z]', ''))
         = 'reviewedteu'
     AND COALESCE(
           TRY_TO_TIMESTAMP(CAST(a.date_time AS STRING),
                            'yyyyMMddHHmmss.SSS'),
           TRY_TO_TIMESTAMP(CAST(a.date_time AS STRING),
                            'yyyyMMddHHmmss'),
           TRY_CAST(a.date_time AS TIMESTAMP)
         ) = TRY_TO_TIMESTAMP(CAST(p.raw_update_time AS STRING),
                              'yyyyMMddHHmmss.SSS')
     AND TRY_CAST(a.change_to AS DECIMAL(18,3))
       - TRY_CAST(a.change_from AS DECIMAL(18,3)) = p.delta_teu
    THEN a.uuid END) AS matching_finalization_audits
FROM {pairs} p
LEFT JOIN datasources.csal.csal_audit_trail a
  ON CAST(a.csal_id AS STRING) = p.csal_id
GROUP BY p.pair_key, p.csal_id, p.side
""")

# Current association and booking route are used only as a technical route check.
# They do not reconstruct the route or ownership at the revision date.
assoc = make_view("assoc", f"""
WITH ranked AS (
  SELECT
    CAST(a.csal_id AS STRING) AS csal_id,
    UPPER(TRIM(a.shipment_num)) AS shipment_num,
    UPPER(TRIM(a.service)) AS service,
    UPPER(TRIM(a.week_num)) AS plan_week,
    UPPER(TRIM(a.sail_week)) AS association_sail_week,
    a.match_ind,
    DENSE_RANK() OVER (
      PARTITION BY a.csal_id, UPPER(TRIM(a.shipment_num))
      ORDER BY a.rec_upd_dt_utc DESC NULLS LAST,
               a.rec_cre_dt_utc DESC NULLS LAST
    ) AS latest_rank
  FROM datasources.csal.csal_booking_assoc_evt a
  LEFT SEMI JOIN (SELECT DISTINCT csal_id FROM {pairs}) p
    ON CAST(a.csal_id AS STRING) = p.csal_id
  WHERE NULLIF(TRIM(a.shipment_num), '') IS NOT NULL
), latest AS (
  SELECT *, COUNT(*) OVER (PARTITION BY csal_id, shipment_num)
    AS current_assoc_rows
  FROM ranked WHERE latest_rank = 1
)
SELECT * FROM latest
""")

detail = make_view("detail", f"""
WITH ranked AS (
  SELECT
    UPPER(TRIM(d.shipment_num)) AS shipment_num,
    REGEXP_REPLACE(UPPER(TRIM(d.corp_svc_cde)), '-[NESW]$', '')
      AS base_service,
    UPPER(TRIM(d.corp_vsl_cde)) AS vessel_code,
    UPPER(TRIM(d.corp_voy_num)) AS voyage_number,
    CASE UPPER(TRIM(d.corp_voy_dir))
      WHEN 'NORTH' THEN 'N' WHEN 'SOUTH' THEN 'S'
      WHEN 'EAST' THEN 'E' WHEN 'WEST' THEN 'W'
      ELSE UPPER(TRIM(d.corp_voy_dir)) END AS direction,
    UPPER(TRIM(d.lpol_port_cde)) AS loading_port,
    UPPER(TRIM(d.sail_week)) AS booking_sail_week,
    DENSE_RANK() OVER (
      PARTITION BY UPPER(TRIM(d.shipment_num))
      ORDER BY d.rec_upd_dt_utc DESC NULLS LAST,
               d.rec_cre_dt_utc DESC NULLS LAST
    ) AS latest_rank
  FROM datasources.csal.csal_booking_detail d
  LEFT SEMI JOIN (SELECT DISTINCT shipment_num FROM {assoc}) a
    ON UPPER(TRIM(d.shipment_num)) = a.shipment_num
), latest AS (
  SELECT *, COUNT(*) OVER (PARTITION BY shipment_num)
    AS current_detail_rows
  FROM ranked WHERE latest_rank = 1
)
SELECT *,
  CONCAT(vessel_code,
    CASE WHEN LENGTH(voyage_number) < 3
         THEN LPAD(voyage_number, 3, '0')
         ELSE voyage_number END) AS short_voyage,
  CONCAT(base_service, '-', vessel_code, '-',
    CASE WHEN LENGTH(voyage_number) < 3
         THEN LPAD(voyage_number, 3, '0')
         ELSE voyage_number END,
    ' ', direction) AS corporate_svvd
FROM latest
""")

stops = make_view("stops", """
WITH ranked AS (
  SELECT
    CAST(id AS STRING) AS stop_id,
    COALESCE(NULLIF(UPPER(TRIM(msg_business_key)), ''),
             CONCAT('ID:', CAST(id AS STRING))) AS stop_identity,
    UPPER(TRIM(port_code)) AS loading_port,
    CASE
      WHEN use_dep_svvd = TRUE
        THEN REGEXP_REPLACE(UPPER(TRIM(dep_svvd)), ' +', ' ')
      WHEN use_dep_svvd = FALSE
        THEN REGEXP_REPLACE(UPPER(TRIM(arr_svvd)), ' +', ' ')
    END AS effective_svvd,
    UPPER(TRIM(sail_week)) AS stop_sail_week,
    is_load_allowed, is_omitted, is_tentative_schedule,
    is_vms, is_phase_out, private_call,
    tcr_cutoff_date AS cutoff_raw,
    TRY_CAST(SUBSTR(CAST(tcr_cutoff_date AS STRING), 1, 10)
             AS DATE) AS cutoff_utc_date,
    DENSE_RANK() OVER (
      PARTITION BY COALESCE(NULLIF(UPPER(TRIM(msg_business_key)), ''),
                           CONCAT('ID:', CAST(id AS STRING)))
      ORDER BY rec_upd_dt_utc DESC NULLS LAST,
               rec_cre_dt_utc DESC NULLS LAST
    ) AS latest_rank
  FROM datasources.csal.csal_voy_stop_dtl
), latest AS (
  SELECT *, COUNT(*) OVER (PARTITION BY stop_identity)
    AS current_stop_rows
  FROM ranked WHERE latest_rank = 1
)
SELECT * FROM latest
""")

route_rows = make_view("route_rows", f"""
SELECT
  p.pair_key, p.csal_id, p.side,
  a.shipment_num, a.current_assoc_rows,
  a.association_sail_week, p.plan_week,
  d.current_detail_rows, d.booking_sail_week,
  d.corporate_svvd, d.loading_port,
  s.stop_id, s.stop_identity, s.stop_sail_week,
  s.cutoff_raw, s.cutoff_utc_date,
  CASE WHEN a.match_ind = TRUE
         AND a.current_assoc_rows = 1
         AND a.service = p.service
         AND a.plan_week = p.plan_week
         AND d.current_detail_rows = 1
         AND d.base_service = REGEXP_REPLACE(p.service, '-[NESW]$', '')
         AND d.short_voyage =
             REGEXP_REPLACE(p.short_voyage, '[^A-Z0-9]', '')
         AND d.direction IN ('N', 'S', 'E', 'W')
         AND d.loading_port IS NOT NULL
         AND s.stop_id IS NOT NULL
         AND s.current_stop_rows = 1
         AND s.is_load_allowed = TRUE
         AND s.is_omitted = FALSE
         AND s.is_tentative_schedule = FALSE
         AND s.is_vms = FALSE
         AND s.is_phase_out = FALSE
         AND s.private_call = FALSE
         AND s.cutoff_utc_date IS NOT NULL
         AND d.booking_sail_week IS NOT NULL
         AND s.stop_sail_week = d.booking_sail_week
       THEN TRUE ELSE FALSE END AS exact_current_stop
FROM {pairs} p
LEFT JOIN {assoc} a ON p.csal_id = a.csal_id
LEFT JOIN {detail} d ON a.shipment_num = d.shipment_num
LEFT JOIN {stops} s
  ON d.loading_port = s.loading_port
 AND d.corporate_svvd = s.effective_svvd
""")

side_route = make_view("side_route", f"""
SELECT
  pair_key, csal_id, side,
  COUNT(DISTINCT shipment_num) AS associated_shipments,
  COUNT(DISTINCT CASE WHEN stop_id IS NOT NULL
                      THEN shipment_num END) AS stop_matched_shipments,
  COUNT(DISTINCT CASE WHEN stop_id IS NOT NULL
                       AND booking_sail_week IS NOT NULL
                       AND booking_sail_week = stop_sail_week
                      THEN shipment_num END) AS week_aligned_shipments,
  COUNT(DISTINCT CASE WHEN exact_current_stop
                      THEN shipment_num END) AS exact_shipments,
  COUNT(DISTINCT CASE WHEN exact_current_stop
                      THEN stop_identity END) AS exact_stops,
  COUNT(DISTINCT stop_identity) AS all_matched_stops,
  COUNT(DISTINCT CASE WHEN exact_current_stop
                      THEN cutoff_raw END) AS exact_cutoff_values,
  MIN(CASE WHEN exact_current_stop THEN cutoff_utc_date END)
    AS cutoff_utc_date,
  MIN(CASE WHEN exact_current_stop THEN corporate_svvd END)
    AS exact_corporate_svvd,
  MIN(CASE WHEN exact_current_stop THEN stop_sail_week END)
    AS example_stop_week,
  MIN(CASE WHEN exact_current_stop THEN booking_sail_week END)
    AS example_booking_week,
  MIN(association_sail_week) AS example_association_week,
  MIN(booking_sail_week) AS example_booking_week_any,
  MIN(stop_sail_week) AS example_stop_week_any
FROM {route_rows}
GROUP BY pair_key, csal_id, side
""")

pair_status = make_view("pair_status", f"""
WITH side AS (
  SELECT p.pair_key, p.service, p.plan_week, p.short_voyage,
         p.raw_update_time, p.raw_update_date, p.candidate_teu,
         p.side, p.csal_id,
         r.associated_shipments, r.stop_matched_shipments,
         r.week_aligned_shipments, r.exact_shipments,
         r.exact_stops, r.all_matched_stops,
         r.exact_cutoff_values, r.cutoff_utc_date,
         r.exact_corporate_svvd,
         a.matching_finalization_audits,
         CASE
           WHEN r.associated_shipments = 0 THEN 'NO_CURRENT_ASSOCIATION'
           WHEN r.stop_matched_shipments > 0
            AND r.week_aligned_shipments <> r.associated_shipments
             THEN 'BOOKING_STOP_WEEK_UNRESOLVED'
           WHEN r.exact_shipments <> r.associated_shipments
             THEN 'ROUTE_OR_STOP_UNRESOLVED'
           WHEN r.exact_stops <> 1 OR r.all_matched_stops <> 1
             OR r.exact_cutoff_values <> 1
             THEN 'MULTIPLE_CURRENT_STOPS_OR_CUTOFFS'
           ELSE 'ONE_EXACT_CURRENT_STOP'
         END AS route_status
  FROM {pairs} p
  JOIN {side_route} r
    ON p.pair_key = r.pair_key
   AND p.csal_id = r.csal_id
   AND p.side = r.side
  JOIN {audit_side} a
    ON p.pair_key = a.pair_key
   AND p.csal_id = a.csal_id
   AND p.side = a.side
)
SELECT
  pair_key,
  MAX(service) AS service,
  MAX(plan_week) AS plan_week,
  MAX(short_voyage) AS short_voyage,
  MAX(raw_update_time) AS raw_update_time,
  MAX(raw_update_date) AS raw_update_date,
  MAX(candidate_teu) AS candidate_teu,
  MAX(CASE WHEN side = 'DECREASE' THEN route_status END)
    AS decrease_route_status,
  MAX(CASE WHEN side = 'INCREASE' THEN route_status END)
    AS increase_route_status,
  MAX(CASE WHEN side = 'DECREASE' THEN cutoff_utc_date END)
    AS decrease_cutoff_utc_date,
  MAX(CASE WHEN side = 'INCREASE' THEN cutoff_utc_date END)
    AS increase_cutoff_utc_date,
  MAX(CASE WHEN side = 'DECREASE' THEN exact_corporate_svvd END)
    AS decrease_svvd,
  MAX(CASE WHEN side = 'INCREASE' THEN exact_corporate_svvd END)
    AS increase_svvd,
  MIN(matching_finalization_audits) AS minimum_side_audit_matches,
  CASE
    WHEN MIN(CASE WHEN route_status = 'ONE_EXACT_CURRENT_STOP'
                  THEN 1 ELSE 0 END) = 1
     AND MIN(CASE WHEN matching_finalization_audits > 0
                  THEN 1 ELSE 0 END) = 1
     AND MAX(CASE WHEN side = 'DECREASE' THEN exact_corporate_svvd END)
       = MAX(CASE WHEN side = 'INCREASE' THEN exact_corporate_svvd END)
      THEN 'BOTH_SIDES_EXACT_AND_AUDITED'
    ELSE 'CUTOFF_OR_AUDIT_UNRESOLVED'
  END AS evidence_status
FROM side
GROUP BY pair_key
""")

show("0. Source and cutoff coverage by service and month", f"""
WITH source AS (
  SELECT UPPER(TRIM(service)) AS service,
         SUBSTR(updated_on, 1, 6) AS update_month,
         COUNT(*) AS finalized_rows,
         SUM(CASE WHEN TRY_CAST(last_reviewed_teu AS DECIMAL(18,3))
                         IS NOT NULL
                   AND TRY_CAST(reviewed_teu AS DECIMAL(18,3))
                         IS NOT NULL
                   AND NULLIF(TRIM(week_num), '') IS NOT NULL
                   AND NULLIF(TRIM(vessel_voyage), '') IS NOT NULL
                  THEN 1 ELSE 0 END) AS analyzable_rows
  FROM datasources.csal.csal_change_log
  WHERE COALESCE(deleted, FALSE) = FALSE
    AND UPPER(TRIM(status)) = 'FINALIZED'
    AND UPPER(TRIM(acceptance_status)) = 'TCC ACCEPTED'
    AND updated_on RLIKE '^[0-9]{{14}}[.][0-9]{{3}}$'
    AND SUBSTR(updated_on, 1, 8) >= '{START_DAY}'
    AND TRY_TO_TIMESTAMP(CAST(updated_on AS STRING),
                         'yyyyMMddHHmmss.SSS') IS NOT NULL
    AND NULLIF(TRIM(service), '') IS NOT NULL
  GROUP BY UPPER(TRIM(service)), SUBSTR(updated_on, 1, 6)
), paired AS (
  SELECT service, DATE_FORMAT(raw_update_date, 'yyyyMM') AS update_month,
         COUNT(*) AS balanced_pair_candidates,
         SUM(CASE WHEN evidence_status = 'BOTH_SIDES_EXACT_AND_AUDITED'
                  THEN 1 ELSE 0 END) AS pairs_with_usable_cutoff
  FROM {pair_status}
  GROUP BY service, DATE_FORMAT(raw_update_date, 'yyyyMM')
)
SELECT s.service, s.update_month, s.finalized_rows,
       s.analyzable_rows,
       ROUND(100.0 * s.analyzable_rows / s.finalized_rows, 1)
         AS analyzable_pct,
       COALESCE(p.balanced_pair_candidates, 0)
         AS balanced_pair_candidates,
       COALESCE(p.pairs_with_usable_cutoff, 0)
         AS pairs_with_usable_cutoff
FROM source s
LEFT JOIN paired p
  ON s.service = p.service AND s.update_month = p.update_month
ORDER BY s.service, s.update_month
""")

show("1. Recorded allocation revisions by raw update weekday", f"""
SELECT service,
       DATE_FORMAT(raw_update_date, 'EEEE') AS raw_calendar_weekday,
       COUNT(*) AS value_change_rows,
       COUNT(DISTINCT csal_id) AS plans,
       ROUND(SUM(CASE WHEN delta_teu > 0 THEN delta_teu ELSE 0 END), 1)
         AS increase_teu,
       ROUND(-SUM(CASE WHEN delta_teu < 0 THEN delta_teu ELSE 0 END), 1)
         AS decrease_teu
FROM {changes}
WHERE delta_teu <> 0
GROUP BY service, DATE_FORMAT(raw_update_date, 'EEEE')
ORDER BY service, raw_calendar_weekday
""")

show("1a. Revision timing around Monday three weeks before plan week", f"""
WITH parsed AS (
  SELECT *,
         TRY_CAST(CONCAT(SUBSTR(plan_week, 1, 4), '-01-04')
                  AS DATE) AS january_fourth,
         CAST(SUBSTR(plan_week, 7, 2) AS INT) AS week_number
  FROM {changes}
  WHERE delta_teu <> 0
    AND plan_week RLIKE '^[0-9]{{4}}WK(0[1-9]|[1-4][0-9]|5[0-3])$'
), planning AS (
  SELECT *,
         DATE_SUB(
           DATE_ADD(
             DATE_SUB(january_fourth,
                      PMOD(DAYOFWEEK(january_fourth) + 5, 7)),
             7 * (week_number - 1)),
           21) AS planning_monday
  FROM parsed
  WHERE january_fourth IS NOT NULL
)
SELECT service,
       CASE WHEN raw_update_date < planning_monday
              THEN 'Before planning Monday'
            WHEN raw_update_date = planning_monday
              THEN 'On planning Monday'
            ELSE 'After planning Monday' END AS calendar_position,
       COUNT(*) AS value_change_rows,
       ROUND(SUM(ABS(delta_teu)), 1) AS changed_teu
FROM planning
GROUP BY service,
         CASE WHEN raw_update_date < planning_monday
                THEN 'Before planning Monday'
              WHEN raw_update_date = planning_monday
                THEN 'On planning Monday'
              ELSE 'After planning Monday' END
ORDER BY service, calendar_position
""")

show("2. Balanced-pair screening and cutoff evidence by service", f"""
SELECT service, COUNT(*) AS balanced_pair_candidates,
       SUM(CASE WHEN evidence_status = 'BOTH_SIDES_EXACT_AND_AUDITED'
                THEN 1 ELSE 0 END) AS pairs_with_usable_cutoff,
       SUM(CASE WHEN evidence_status <> 'BOTH_SIDES_EXACT_AND_AUDITED'
                THEN 1 ELSE 0 END) AS unresolved_pairs,
       ROUND(SUM(candidate_teu), 1) AS candidate_teu,
       ROUND(SUM(CASE WHEN evidence_status = 'BOTH_SIDES_EXACT_AND_AUDITED'
                 THEN candidate_teu ELSE 0 END), 1) AS usable_cutoff_teu
FROM {pair_status}
GROUP BY service
ORDER BY balanced_pair_candidates DESC, service
""")

show("3. Daily allocation revision activity, all services", f"""
SELECT service, raw_update_date,
       DATE_FORMAT(raw_update_date, 'EEEE') AS raw_calendar_weekday,
       CASE WHEN delta_teu > 0 THEN 'Increase' ELSE 'Decrease' END
         AS direction,
       COUNT(*) AS value_change_rows,
       ROUND(SUM(ABS(delta_teu)), 1) AS changed_teu
FROM {changes}
WHERE delta_teu <> 0
GROUP BY service, raw_update_date,
         CASE WHEN delta_teu > 0 THEN 'Increase' ELSE 'Decrease' END
ORDER BY raw_update_date, service, direction
""")

show("4. Candidate raw update dates relative to current cutoff", f"""
WITH usable AS (
  SELECT *,
         LEAST(decrease_cutoff_utc_date, increase_cutoff_utc_date)
           AS binding_cutoff_utc_date
  FROM {pair_status}
  WHERE evidence_status = 'BOTH_SIDES_EXACT_AND_AUDITED'
)
SELECT service,
       DATEDIFF(raw_update_date, binding_cutoff_utc_date)
         AS raw_day_minus_utc_cutoff_day,
       DATE_FORMAT(raw_update_date, 'EEEE') AS raw_calendar_weekday,
       COUNT(*) AS candidate_pairs,
       ROUND(SUM(candidate_teu), 1) AS candidate_teu
FROM usable
GROUP BY service,
         DATEDIFF(raw_update_date, binding_cutoff_utc_date),
         DATE_FORMAT(raw_update_date, 'EEEE')
ORDER BY service, raw_day_minus_utc_cutoff_day
""")

show("5. Why candidate pairs cannot yet be placed on a cutoff timeline", f"""
SELECT service, evidence_status,
       decrease_route_status, increase_route_status,
       COUNT(*) AS candidate_pairs,
       ROUND(SUM(candidate_teu), 1) AS candidate_teu
FROM {pair_status}
GROUP BY service, evidence_status,
         decrease_route_status, increase_route_status
ORDER BY service, candidate_pairs DESC
""")

show("6. Week-context coverage for candidate plan sides", f"""
SELECT p.service,
       COUNT(*) AS candidate_plan_sides,
       SUM(r.associated_shipments) AS associated_shipment_sides,
       SUM(r.stop_matched_shipments) AS svvd_port_stop_matched_sides,
       SUM(r.week_aligned_shipments) AS booking_stop_week_aligned_sides,
       SUM(CASE WHEN r.associated_shipments > 0
                 AND r.exact_shipments = r.associated_shipments
                 AND r.exact_stops = 1
                 AND r.all_matched_stops = 1
                 AND r.exact_cutoff_values = 1
                THEN 1 ELSE 0 END) AS sides_with_one_strict_cutoff
FROM {pairs} p
JOIN {side_route} r
  ON p.pair_key = r.pair_key
 AND p.csal_id = r.csal_id
 AND p.side = r.side
GROUP BY p.service
ORDER BY p.service
""")

print("\nTemporary views:", changes, groups, pairs, pair_status)
print("Raw change-log/audit timezone is unconfirmed. Output 4 compares raw dates"
      " with UTC cutoff dates; it is a provisional calendar-day view, not"
      " a precise before/after cutoff rate. The binding cutoff is the earlier"
      " of two exact current stop candidates. Booking and stop sail weeks"
      " must agree; plan week is shown separately and is not equated to them."
      " Current routes may differ from"
      " routes at finalization. Equal opposite changes are candidates, not"
      " confirmed swaps. No source table was changed.")
