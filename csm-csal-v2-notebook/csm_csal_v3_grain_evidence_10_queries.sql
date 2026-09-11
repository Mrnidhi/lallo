-- CSM/CSAL V3 grain evidence
-- Read-only. Frozen source: Delta version 80, August 2026.

-- E01: total booked TEU at booking grain
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
booking AS (
  SELECT customer, agreement, week_num, service, tcr,
         MAX(booked_teu) AS booked_teu
  FROM source
  GROUP BY customer, agreement, week_num, service, tcr
),
totals AS (
  SELECT (SELECT SUM(booked_teu) FROM source) AS wide_row_total,
         (SELECT SUM(booked_teu) FROM booking) AS correct_total
)
SELECT 'E01' AS test_id, wide_row_total, correct_total,
       wide_row_total - correct_total AS repeated_amount,
       ROUND(100.0 * (wide_row_total - correct_total) /
             NULLIF(correct_total, 0), 6) AS repeated_amount_pct
FROM totals;

-- E02: total reviewed commitment at commitment grain
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
commitment AS (
  SELECT customer, agreement, week_num, service,
         MAX(total_reviewed_teu) AS total_reviewed_teu
  FROM source
  GROUP BY customer, agreement, week_num, service
),
totals AS (
  SELECT (SELECT SUM(total_reviewed_teu) FROM source) AS wide_row_total,
         (SELECT SUM(total_reviewed_teu) FROM commitment) AS correct_total
)
SELECT 'E02' AS test_id, wide_row_total, correct_total,
       wide_row_total - correct_total AS repeated_amount,
       ROUND(100.0 * (wide_row_total - correct_total) /
             NULLIF(correct_total, 0), 6) AS repeated_amount_pct
FROM totals;

-- E03: monthly reviewed TEU at monthly grain
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
monthly AS (
  SELECT month, customer, sales_rep, agreement, service,
         MAX(monthly_reviewed_teu) AS monthly_reviewed_teu
  FROM source
  GROUP BY month, customer, sales_rep, agreement, service
),
totals AS (
  SELECT (SELECT SUM(monthly_reviewed_teu) FROM source) AS wide_row_total,
         (SELECT SUM(monthly_reviewed_teu) FROM monthly) AS correct_total
)
SELECT 'E03' AS test_id, wide_row_total, correct_total,
       wide_row_total - correct_total AS repeated_amount,
       ROUND(100.0 * (wide_row_total - correct_total) /
             NULLIF(correct_total, 0), 6) AS repeated_amount_pct
FROM totals;

-- E04: SC MQC at agreement grain
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
agreement_context AS (
  SELECT agreement, MAX(sc_mqc) AS sc_mqc
  FROM source
  GROUP BY agreement
),
totals AS (
  SELECT (SELECT SUM(sc_mqc) FROM source) AS wide_row_total,
         (SELECT SUM(sc_mqc) FROM agreement_context) AS correct_total
)
SELECT 'E04' AS test_id, wide_row_total, correct_total,
       wide_row_total - correct_total AS repeated_amount,
       ROUND(100.0 * (wide_row_total - correct_total) /
             NULLIF(correct_total, 0), 6) AS repeated_amount_pct
FROM totals;

-- E05: allocation-grain control
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
allocation AS (
  SELECT month, week_num, customer, sales_rep, agreement, tcr,
         service, category, MAX(reviewed_teu) AS reviewed_teu
  FROM source
  GROUP BY month, week_num, customer, sales_rep, agreement, tcr,
           service, category
)
SELECT 'E05' AS test_id,
       (SELECT COUNT(*) FROM source) AS wide_rows,
       (SELECT COUNT(*) FROM allocation) AS allocation_rows,
       (SELECT SUM(reviewed_teu) FROM source) AS wide_row_total,
       (SELECT SUM(reviewed_teu) FROM allocation) AS correct_total;

-- E06: booking combinations repeated across allocation categories
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
booking_profile AS (
  SELECT customer, agreement, week_num, service, tcr,
         COUNT(*) AS allocation_rows,
         COUNT(DISTINCT category) AS category_values,
         COUNT(DISTINCT COALESCE(CAST(is_volume_without_csal AS STRING),
                                 '__NULL__')) AS volume_without_csal_values
  FROM source
  GROUP BY customer, agreement, week_num, service, tcr
)
SELECT 'E06' AS test_id,
       COUNT_IF(category_values > 1) AS combinations_with_multiple_categories,
       COUNT_IF(volume_without_csal_values > 1) AS combinations_with_conflicting_flags,
       MAX(category_values) AS largest_category_count,
       MAX(allocation_rows) AS largest_allocation_row_count
FROM booking_profile;

-- E07: booking combinations with more than one days-to-cutoff value
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
booking_profile AS (
  SELECT customer, agreement, week_num, service, tcr,
         COUNT(DISTINCT COALESCE(CAST(days_to_cutoff AS STRING),
                                 '__NULL__')) AS cutoff_values
  FROM source
  GROUP BY customer, agreement, week_num, service, tcr
)
SELECT 'E07' AS test_id,
       COUNT(*) AS booking_combinations,
       COUNT_IF(cutoff_values > 1) AS combinations_with_multiple_cutoff_values,
       MAX(cutoff_values) AS maximum_cutoff_values_in_one_combination
FROM booking_profile;

-- E08: TCR detail with commitment shown once
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
selected_scope AS (
  SELECT customer, agreement, week_num, service,
         COUNT(DISTINCT tcr) AS tcr_count
  FROM source
  WHERE customer IS NOT NULL AND agreement IS NOT NULL
    AND week_num IS NOT NULL AND service IS NOT NULL
  GROUP BY customer, agreement, week_num, service
  HAVING COUNT(DISTINCT tcr) > 1
  ORDER BY tcr_count DESC, customer, agreement, week_num, service
  LIMIT 1
),
booking AS (
  SELECT source.customer, source.agreement, source.week_num, source.service,
         source.tcr, MAX(source.confirmed_teu) AS confirmed_teu,
         MAX(source.booked_teu) AS booked_teu
  FROM source
  INNER JOIN selected_scope
    ON source.customer = selected_scope.customer
   AND source.agreement = selected_scope.agreement
   AND source.week_num = selected_scope.week_num
   AND source.service = selected_scope.service
  GROUP BY source.customer, source.agreement, source.week_num,
           source.service, source.tcr
),
commitment AS (
  SELECT source.customer, source.agreement, source.week_num, source.service,
         MAX(source.total_reviewed_teu) AS total_reviewed_teu
  FROM source
  INNER JOIN selected_scope
    ON source.customer = selected_scope.customer
   AND source.agreement = selected_scope.agreement
   AND source.week_num = selected_scope.week_num
   AND source.service = selected_scope.service
  GROUP BY source.customer, source.agreement, source.week_num, source.service
)
SELECT 'E08 TCR DETAIL' AS result_type, customer, agreement, week_num,
       service, tcr, confirmed_teu, booked_teu,
       CAST(NULL AS BIGINT) AS total_reviewed_teu
FROM booking
UNION ALL
SELECT 'E08 COMMITMENT TOTAL' AS result_type, customer, agreement, week_num,
       service, CAST(NULL AS STRING) AS tcr,
       CAST(NULL AS BIGINT) AS confirmed_teu,
       CAST(NULL AS BIGINT) AS booked_teu, total_reviewed_teu
FROM commitment
ORDER BY result_type DESC, tcr;

-- E09: weighted overall cancellation percentage
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
booking AS (
  SELECT customer, agreement, week_num, service, tcr,
         MAX(cancelled_teu) AS cancelled_teu,
         MAX(booked_teu) AS booked_teu,
         MAX(cancellation_rate) AS stored_cancellation_rate
  FROM source
  GROUP BY customer, agreement, week_num, service, tcr
),
comparison AS (
  SELECT 100.0 * SUM(cancelled_teu) / NULLIF(SUM(booked_teu), 0)
           AS correct_overall_cancellation_pct,
         AVG(stored_cancellation_rate) AS unweighted_average_of_stored_rates
  FROM booking
)
SELECT 'E09' AS test_id,
       ROUND(correct_overall_cancellation_pct, 6)
         AS correct_overall_cancellation_pct,
       ROUND(unweighted_average_of_stored_rates, 6)
         AS unweighted_average_of_stored_rates,
       ROUND(unweighted_average_of_stored_rates -
             correct_overall_cancellation_pct, 6)
         AS percentage_point_difference
FROM comparison;

-- E10: missing identities remain visible
WITH source AS (
  SELECT *
  FROM dev.sales_ai_assistant_gold.csm_csal_summary VERSION AS OF 80
  WHERE month = 'August 2026'
),
classified AS (
  SELECT CASE
    WHEN (agreement IS NULL OR TRIM(agreement) = '')
     AND (sales_rep IS NULL OR TRIM(sales_rep) = '')
      THEN 'MISSING BOTH'
    WHEN agreement IS NULL OR TRIM(agreement) = ''
      THEN 'MISSING AGREEMENT'
    WHEN sales_rep IS NULL OR TRIM(sales_rep) = ''
      THEN 'MISSING SALES REPRESENTATIVE'
    ELSE 'COMPLETE'
  END AS identity_status
  FROM source
)
SELECT 'E10' AS test_id, identity_status, COUNT(*) AS allocation_rows
FROM classified
WHERE identity_status <> 'COMPLETE'
GROUP BY identity_status
ORDER BY identity_status;
