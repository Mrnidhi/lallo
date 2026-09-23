# Databricks Python cell. Run after csal-swap-candidates-notebook-cell.py
# in the same notebook session. Reads its temporary views; creates no tables.
# Counts are aggregate and nonexclusive: one pair can fail several gates.

required = ("pairs", "side_route", "audit_side", "route_rows", "detail")
missing = [name for name in required if name not in globals()]
if missing:
    raise RuntimeError("Run the swap-candidates cell first. Missing: "
                       + ", ".join(missing))
expired = [name for name in required if not spark.catalog.tableExists(globals()[name])]
if expired:
    raise RuntimeError("Swap-candidate temporary views expired. Rerun that cell: "
                       + ", ".join(expired))

print("Balanced-pair evidence gates by service. Failure counts overlap; no pair is a confirmed swap.")
display(spark.sql(f"""
WITH side AS (
  SELECT p.pair_key, p.csal_id, p.side, p.service,
         MAX(r.associated_shipments) AS associations,
         MAX(r.stop_matched_shipments) AS stop_matches,
         MAX(r.week_aligned_shipments) AS week_matches,
         MAX(r.exact_shipments) AS exact_shipments,
         MAX(r.exact_stops) AS exact_stops,
         MAX(r.all_matched_stops) AS all_stops,
         MAX(r.exact_cutoff_values) AS exact_cutoffs,
         MAX(r.exact_corporate_svvd) AS exact_svvd,
         MAX(a.matching_finalization_audits) AS audit_matches,
         MAX(CASE WHEN rr.shipment_num IS NOT NULL
                        AND rr.booking_sail_week IS NULL
                  THEN 1 ELSE 0 END) AS missing_detail_week,
         MAX(CASE WHEN rr.stop_id IS NOT NULL
                        AND rr.stop_sail_week IS NULL
                  THEN 1 ELSE 0 END) AS missing_stop_week,
         MAX(CASE WHEN rr.stop_id IS NOT NULL
                        AND rr.booking_sail_week IS NOT NULL
                        AND rr.stop_sail_week IS NOT NULL
                        AND rr.booking_sail_week <> rr.stop_sail_week
                  THEN 1 ELSE 0 END) AS different_weeks,
         MAX(CASE WHEN p.short_voyage LIKE '%,%'
                  THEN 1 ELSE 0 END) AS comma_voyage,
         MAX(CASE WHEN p.short_voyage LIKE '%,%'
                        AND d.short_voyage IS NOT NULL
                        AND ARRAY_CONTAINS(
                          SPLIT(REGEXP_REPLACE(p.short_voyage,
                                               '[^A-Z0-9,]', ''), ','),
                          d.short_voyage)
                  THEN 1 ELSE 0 END) AS comma_member_in_detail
  FROM {pairs} p
  LEFT JOIN {side_route} r
    ON p.pair_key = r.pair_key AND p.csal_id = r.csal_id
   AND p.side = r.side
  LEFT JOIN {audit_side} a
    ON p.pair_key = a.pair_key AND p.csal_id = a.csal_id
   AND p.side = a.side
  LEFT JOIN {route_rows} rr
    ON p.pair_key = rr.pair_key AND p.csal_id = rr.csal_id
   AND p.side = rr.side
  LEFT JOIN {detail} d ON rr.shipment_num = d.shipment_num
  GROUP BY p.pair_key, p.csal_id, p.side, p.service
), pair AS (
  SELECT pair_key, MAX(service) AS service,
         MAX(CASE WHEN COALESCE(associations, 0) = 0
                  THEN 1 ELSE 0 END) AS no_association,
         MAX(CASE WHEN associations > 0 AND stop_matches = 0
                  THEN 1 ELSE 0 END) AS no_port_svvd_stop,
         MAX(CASE WHEN associations > stop_matches
                  THEN 1 ELSE 0 END) AS some_shipments_lack_stop,
         MAX(CASE WHEN stop_matches > 0 AND week_matches < associations
                  THEN 1 ELSE 0 END) AS week_gate_fails,
         MAX(missing_detail_week) AS missing_detail_week,
         MAX(missing_stop_week) AS missing_stop_week,
         MAX(different_weeks) AS different_weeks,
         MAX(CASE WHEN all_stops > 1 OR exact_stops > 1
                        OR exact_cutoffs > 1
                  THEN 1 ELSE 0 END) AS multiple_stops_or_cutoffs,
         MAX(comma_voyage) AS comma_voyage,
         MAX(comma_member_in_detail) AS comma_member_in_detail,
         MAX(CASE WHEN COALESCE(audit_matches, 0) = 0
                  THEN 1 ELSE 0 END) AS audit_mismatch,
         MIN(CASE WHEN audit_matches > 0 THEN 1 ELSE 0 END) AS both_audited,
         MIN(CASE WHEN associations > 0
                        AND exact_shipments = associations
                        AND exact_stops = 1 AND all_stops = 1
                        AND exact_cutoffs = 1
                  THEN 1 ELSE 0 END) AS both_strict_routes,
         MAX(CASE WHEN side = 'DECREASE' THEN exact_svvd END) AS decrease_svvd,
         MAX(CASE WHEN side = 'INCREASE' THEN exact_svvd END) AS increase_svvd
  FROM side
  GROUP BY pair_key
)
SELECT COALESCE(service, 'ALL SERVICES') AS service,
       COUNT(*) AS balanced_pairs,
       SUM(no_association) AS pairs_no_association,
       SUM(no_port_svvd_stop) AS pairs_no_port_svvd_stop,
       SUM(some_shipments_lack_stop) AS pairs_with_stop_gap,
       SUM(week_gate_fails) AS pairs_failing_week_gate,
       SUM(missing_detail_week) AS pairs_missing_detail_week,
       SUM(missing_stop_week) AS pairs_missing_stop_week,
       SUM(different_weeks) AS pairs_different_weeks,
       SUM(multiple_stops_or_cutoffs) AS pairs_multiple_stops_or_cutoffs,
       SUM(comma_voyage) AS pairs_comma_voyage,
       SUM(comma_member_in_detail) AS pairs_comma_member_in_detail,
       SUM(audit_mismatch) AS pairs_audit_mismatch,
       SUM(both_audited) AS pairs_both_audited,
       SUM(both_strict_routes) AS pairs_both_strict_routes,
       SUM(CASE WHEN both_audited = 1 AND both_strict_routes = 1
                     AND decrease_svvd = increase_svvd
                THEN 1 ELSE 0 END) AS pairs_passing_all_gates
FROM pair
GROUP BY ROLLUP(service)
ORDER BY GROUPING(service) DESC, service
"""))

print("A comma-list/detail match shows a possible voyage-normalization issue. "
      "Missing or different sail weeks are diagnostics; do not fill or equate "
      "them without source validation. Current routes may differ from routes "
      "at finalization; this cell assigns no cutoff and changes no source data.")
