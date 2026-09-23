# Databricks Python cell. Run after the swap-candidates cell in the same session.
# Reads temporary views only; output is aggregate across all services.
required = ("pairs", "side_route", "audit_side", "route_rows", "detail")
missing = [x for x in required if x not in globals()]
if missing:
    raise RuntimeError("Run the swap-candidates cell first: " + ", ".join(missing))
expired = [x for x in required if not spark.catalog.tableExists(globals()[x])]
if expired:
    raise RuntimeError("Temporary views expired; rerun the swap-candidates cell: "
                       + ", ".join(expired))

result = spark.sql(f"""
WITH side AS (
  SELECT p.pair_key, p.csal_id, p.side,
         MAX(r.associated_shipments) AS associations,
         MAX(r.stop_matched_shipments) AS matched_stops,
         MAX(r.week_aligned_shipments) AS aligned_weeks,
         MAX(r.exact_shipments) AS exact_shipments,
         MAX(r.exact_stops) AS exact_stops,
         MAX(r.all_matched_stops) AS all_stops,
         MAX(r.exact_cutoff_values) AS exact_cutoffs,
         MAX(r.exact_corporate_svvd) AS exact_svvd,
         MAX(a.matching_finalization_audits) AS audits,
         COUNT(DISTINCT CASE WHEN rr.current_assoc_rows = 1
                               AND rr.current_detail_rows = 1
                             THEN rr.shipment_num END) AS unique_shipments,
         COUNT(DISTINCT rr.cutoff_raw) AS matched_cutoff_values,
         MAX(IF(rr.shipment_num IS NOT NULL
                AND rr.booking_sail_week IS NULL, 1, 0)) AS missing_booking_week,
         MAX(IF(rr.stop_id IS NOT NULL AND rr.stop_sail_week IS NULL,
                1, 0)) AS missing_stop_week,
         MAX(IF(rr.stop_id IS NOT NULL AND rr.booking_sail_week IS NOT NULL
                AND rr.stop_sail_week IS NOT NULL
                AND rr.booking_sail_week <> rr.stop_sail_week,
                1, 0)) AS different_weeks,
         MAX(IF(p.short_voyage LIKE '%,%', 1, 0)) AS comma_voyage,
         MAX(IF(p.short_voyage LIKE '%,%' AND d.short_voyage IS NOT NULL
                AND ARRAY_CONTAINS(
                  SPLIT(REGEXP_REPLACE(p.short_voyage, '[^A-Z0-9,]', ''), ','),
                  d.short_voyage), 1, 0)) AS comma_member_in_detail
  FROM {pairs} p
  LEFT JOIN {side_route} r ON p.pair_key = r.pair_key
    AND p.csal_id = r.csal_id AND p.side = r.side
  LEFT JOIN {audit_side} a ON p.pair_key = a.pair_key
    AND p.csal_id = a.csal_id AND p.side = a.side
  LEFT JOIN {route_rows} rr ON p.pair_key = rr.pair_key
    AND p.csal_id = rr.csal_id AND p.side = rr.side
  LEFT JOIN {detail} d ON rr.shipment_num = d.shipment_num
  GROUP BY p.pair_key, p.csal_id, p.side
), pair AS (
  SELECT pair_key, COUNT(*) AS side_rows,
         COUNT_IF(audits > 0) AS audit_sides,
         COUNT_IF(associations > 0) AS association_sides,
         COUNT_IF(matched_stops > 0) AS stop_sides,
         COUNT_IF(associations > 0 AND missing_booking_week = 0)
           AS booking_week_sides,
         COUNT_IF(associations > 0 AND aligned_weeks = associations)
           AS aligned_week_sides,
         COUNT_IF(associations > 0 AND unique_shipments = associations)
           AS unique_row_sides,
         COUNT_IF(matched_stops > 0 AND all_stops = 1
                  AND matched_cutoff_values = 1) AS one_stop_sides,
         COUNT_IF(associations > 0 AND exact_shipments = associations
                  AND exact_stops = 1 AND all_stops = 1
                  AND exact_cutoffs = 1) AS strict_sides,
         MAX(IF(COALESCE(associations, 0) = 0, 1, 0)) AS no_association,
         MAX(IF(associations > 0 AND matched_stops = 0, 1, 0)) AS no_stop,
         MAX(missing_booking_week) AS missing_booking_week,
         MAX(missing_stop_week) AS missing_stop_week,
         MAX(different_weeks) AS different_weeks,
         MAX(IF(all_stops > 1 OR matched_cutoff_values > 1, 1, 0))
           AS multiple_stops_or_cutoffs,
         MAX(comma_voyage) AS comma_voyage,
         MAX(comma_member_in_detail) AS comma_member_in_detail,
         MAX(CASE WHEN side = 'DECREASE' THEN exact_svvd END) AS decrease_svvd,
         MAX(CASE WHEN side = 'INCREASE' THEN exact_svvd END) AS increase_svvd
  FROM side GROUP BY pair_key
)
SELECT COUNT(*) AS pairs, SUM(side_rows) AS sides,
       SUM(audit_sides) AS audit_sides, COUNT_IF(audit_sides = 2) AS audit_pairs,
       SUM(association_sides) AS association_sides,
       COUNT_IF(association_sides = 2) AS association_pairs,
       SUM(stop_sides) AS stop_sides, COUNT_IF(stop_sides = 2) AS stop_pairs,
       SUM(booking_week_sides) AS booking_week_sides,
       COUNT_IF(booking_week_sides = 2) AS booking_week_pairs,
       SUM(aligned_week_sides) AS aligned_week_sides,
       COUNT_IF(aligned_week_sides = 2) AS aligned_week_pairs,
       SUM(unique_row_sides) AS unique_row_sides,
       COUNT_IF(unique_row_sides = 2) AS unique_row_pairs,
       SUM(one_stop_sides) AS one_stop_sides,
       COUNT_IF(one_stop_sides = 2) AS one_stop_pairs,
       SUM(strict_sides) AS strict_sides,
       COUNT_IF(strict_sides = 2) AS strict_pairs,
       SUM(no_association) AS no_association,
       SUM(no_stop) AS no_stop,
       SUM(missing_booking_week) AS missing_booking_week,
       SUM(missing_stop_week) AS missing_stop_week,
       SUM(different_weeks) AS different_weeks,
       SUM(multiple_stops_or_cutoffs) AS multiple_stops_or_cutoffs,
       SUM(comma_voyage) AS comma_voyage,
       SUM(comma_member_in_detail) AS comma_member_in_detail,
       COUNT_IF(audit_sides < 2) AS missing_exact_audit,
       COUNT_IF(audit_sides = 2 AND strict_sides = 2
                AND decrease_svvd = increase_svvd) AS all_gates
FROM pair
""").first()

pairs, sides = int(result["pairs"] or 0), int(result["sides"] or 0)
print(f"ALL SERVICES: {pairs:,} balanced pairs / {sides:,} plan sides")
print("Gate                            Passing sides     Pairs with both sides")
for label, key in (
    ("Exact audit", "audit"), ("Current association", "association"),
    ("Exact SVVD + LPOL stop", "stop"),
    ("Booking sail week populated", "booking_week"),
    ("Booking/stop weeks aligned", "aligned_week"),
    ("Unique association/detail rows", "unique_row"),
    ("One matched stop + cutoff", "one_stop"),
    ("Full strict current route", "strict"),
):
    side_n = int(result[key + "_sides"] or 0)
    pair_n = int(result[key + "_pairs"] or 0)
    print(f"{label:<32} {side_n:>5,}/{sides:<5,}       {pair_n:>5,}/{pairs:<5,}")
print("\nFailure clues; pair counts overlap:")
for label, key in (
    ("No association", "no_association"),
    ("No exact stop despite association", "no_stop"),
    ("Booking sail week missing", "missing_booking_week"),
    ("Stop sail week missing", "missing_stop_week"),
    ("Populated weeks disagree", "different_weeks"),
    ("Multiple stops or cutoffs", "multiple_stops_or_cutoffs"),
    ("Comma-separated voyage", "comma_voyage"),
    ("Comma list contains detail voyage", "comma_member_in_detail"),
    ("At least one side lacks exact audit", "missing_exact_audit"),
):
    print(f"{label:<34} {int(result[key] or 0):>5,}")
print(f"Pairs passing all gates: {int(result['all_gates'] or 0):,}")
print("Current routes and sail weeks may differ from finalization-time state. "
      "No cutoff is imputed and no source data is changed.")
