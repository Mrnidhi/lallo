# Databricks Python cell. Run after the corrected swap-candidates cell.
# Read-only aggregate for candidate sides with an exact SVVD + loading-port stop.
if "route_rows" not in globals() or not spark.catalog.tableExists(route_rows):
    raise RuntimeError("Run the corrected swap-candidates cell first.")

display(spark.sql(f"""
WITH matched_side AS (
  SELECT pair_key, csal_id, side,
         COUNT(DISTINCT stop_identity) AS stop_count,
         COUNT(DISTINCT CAST(cutoff_raw AS STRING)) AS cutoff_count,
         MAX(IF(NULLIF(association_sail_week, '') IS NOT NULL, 1, 0))
           AS association_present,
         MAX(IF(NULLIF(booking_sail_week, '') IS NOT NULL, 1, 0))
           AS booking_present,
         MAX(IF(NULLIF(stop_sail_week, '') IS NOT NULL, 1, 0))
           AS stop_present,
         MAX(IF(NULLIF(plan_week, '') IS NOT NULL, 1, 0))
           AS plan_present,
         MIN(IF(association_sail_week IS NOT NULL
                 AND stop_sail_week IS NOT NULL
                 AND association_sail_week = stop_sail_week, 1, 0))
           AS association_equals_stop,
         MIN(IF(booking_sail_week IS NOT NULL
                 AND stop_sail_week IS NOT NULL
                 AND booking_sail_week = stop_sail_week, 1, 0))
           AS booking_equals_stop,
         MIN(IF(plan_week IS NOT NULL
                 AND stop_sail_week IS NOT NULL
                 AND plan_week = stop_sail_week, 1, 0))
           AS plan_equals_stop,
         MIN(IF(plan_week IS NOT NULL
                 AND association_sail_week IS NOT NULL
                 AND plan_week = association_sail_week, 1, 0))
           AS plan_equals_association,
         MIN(IF(plan_week IS NOT NULL
                 AND booking_sail_week IS NOT NULL
                 AND plan_week = booking_sail_week, 1, 0))
           AS plan_equals_booking
  FROM {route_rows}
  WHERE stop_id IS NOT NULL
  GROUP BY pair_key, csal_id, side
)
SELECT COUNT(*) AS matched_stop_sides,
       COUNT(DISTINCT pair_key) AS pairs_with_matched_stop,
       COUNT_IF(stop_count = 1) AS one_stop_sides,
       COUNT_IF(stop_count = 1 AND cutoff_count = 1)
         AS one_stop_one_cutoff_sides,
       COUNT_IF(association_present = 1) AS association_week_present_sides,
       COUNT_IF(booking_present = 1) AS booking_week_present_sides,
       COUNT_IF(stop_present = 1) AS stop_week_present_sides,
       COUNT_IF(plan_present = 1) AS plan_week_present_sides,
       COUNT_IF(stop_count = 1 AND association_equals_stop = 1)
         AS one_stop_association_equals_stop_sides,
       COUNT_IF(stop_count = 1 AND booking_equals_stop = 1)
         AS one_stop_booking_equals_stop_sides,
       COUNT_IF(stop_count = 1 AND plan_equals_stop = 1)
         AS one_stop_plan_equals_stop_sides,
       COUNT_IF(plan_equals_association = 1)
         AS plan_equals_association_sides,
       COUNT_IF(plan_equals_booking = 1) AS plan_equals_booking_sides
FROM matched_side
"""))

print("Week fields are compared separately. Matches do not prove that planning"
      " and actual sailing weeks have the same meaning; no cutoff is assigned.")
