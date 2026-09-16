-- Databricks notebook source
-- DBTITLE 1,CSM/CSAL ten-metric guarded grain audit
-- Read-only. This file creates no table, view or function and changes no configuration.
-- It can establish a downstream repetition pattern. It cannot establish an agent error
-- until the agent trace, version lineage and raw-source validation gates are confirmed.
--
-- Required named parameters in Databricks SQL:
--   report_month                 STRING   Example: August 2026
--   gold_version                INTEGER  Exact Delta version of csm_csal_summary
--   upstream_version            INTEGER  Exact Delta version of csal_teu_performance
--   evidence_id                 STRING   ALL or E01 through E10
--   agent_answer_value          STRING   Blank for ALL; numeric agent answer for one E01-E10 run
--   independent_raw_reference_total STRING Blank until a raw-source rebuild is complete
--   identity_rule_confirmed     INTEGER  0 until an authoritative identity rule is approved; otherwise 1
--   metric_rule_confirmed       INTEGER  0 until metric additivity/status rules are approved; otherwise 1
--   lineage_alignment_confirmed INTEGER  0 until both versions are tied to the same producer run; otherwise 1
--   raw_source_validation_confirmed INTEGER 0 until movement/status source checks pass; otherwise 1
--   agent_trace_executed_confirmed INTEGER 0 until the agent's executed SQL/tool trace is captured; otherwise 1
--   agent_scope_alignment_confirmed INTEGER 0 until source, month, filters and version align; otherwise 1
--   agent_unsafe_aggregation_confirmed INTEGER 0 until the trace shows summation of repeated values; otherwise 1
--
-- Do not substitute CURRENT data for either version. Record both history rows first.

-- COMMAND ----------
-- DBTITLE 1,1. Gold history: capture the selected version row
DESCRIBE HISTORY `dev`.`sales_ai_assistant_gold`.`csm_csal_summary`;

-- COMMAND ----------
-- DBTITLE 1,2. Upstream history: capture the selected version row
DESCRIBE HISTORY `dev`.`crmi_gold`.`csal_teu_performance`;

-- COMMAND ----------
-- DBTITLE 1,3. Confirm the pinned Gold snapshot exists
SELECT
  'GOLD' AS source_layer,
  :gold_version AS pinned_version,
  :report_month AS report_month,
  COUNT(*) AS source_rows,
  MIN(month) AS minimum_selected_month,
  MAX(month) AS maximum_selected_month
FROM `dev`.`sales_ai_assistant_gold`.`csm_csal_summary` VERSION AS OF :gold_version
WHERE month = :report_month;

-- COMMAND ----------
-- DBTITLE 1,4. Confirm the pinned upstream snapshot exists
SELECT
  'UPSTREAM' AS source_layer,
  :upstream_version AS pinned_version,
  :report_month AS report_month,
  COUNT(*) AS source_rows,
  MIN(run_date) AS minimum_run_date,
  MAX(run_date) AS maximum_run_date
FROM `dev`.`crmi_gold`.`csal_teu_performance` VERSION AS OF :upstream_version
WHERE month = :report_month;

-- COMMAND ----------
-- DBTITLE 1,5. Run all ten cases or one selected evidence ID
WITH
metric_catalog AS (
  SELECT * FROM VALUES
    ('E01', 'MONTHLY', 'monthly_booked_teu',    'booked_teu',     'For the selected month, what is total monthly booked TEU?'),
    ('E02', 'MONTHLY', 'monthly_cancelled_teu', 'cancelled_teu',  'For the selected month, what is total monthly cancelled TEU?'),
    ('E03', 'MONTHLY', 'monthly_rejected_teu',  'rejected_teu',   'For the selected month, what is total monthly rejected TEU?'),
    ('E04', 'MONTHLY', 'monthly_confirmed_teu', 'confirmed_teu',  'For the selected month, what is total monthly confirmed TEU?'),
    ('E05', 'BOOKING', 'booked_teu',            'booked_teu',     'For the selected month, what is total booked TEU?'),
    ('E06', 'BOOKING', 'confirmed_teu',         'confirmed_teu',  'For the selected month, what is total confirmed TEU?'),
    ('E07', 'BOOKING', 'cancelled_teu',         'cancelled_teu',  'For the selected month, what is total cancelled TEU?'),
    ('E08', 'BOOKING', 'rejected_teu',          'rejected_teu',   'For the selected month, what is total rejected TEU?'),
    ('E09', 'BOOKING', 'no_show_teu',           'no_show_teu',    'For the selected month, what is total no-show TEU?'),
    ('E10', 'BOOKING', 'terminated_teu',        'terminated_teu', 'For the selected month, what is total terminated TEU?')
  AS t(evidence_id, evidence_scope, gold_metric, upstream_metric, production_question)
),
runtime_raw_inputs AS (
  SELECT
    TRIM(CAST(:agent_answer_value AS STRING)) AS agent_answer_text,
    TRIM(CAST(:independent_raw_reference_total AS STRING)) AS independent_raw_reference_text,
    TRY_CAST(:identity_rule_confirmed AS INT) AS identity_rule_confirmed,
    TRY_CAST(:metric_rule_confirmed AS INT) AS metric_rule_confirmed,
    TRY_CAST(:lineage_alignment_confirmed AS INT) AS lineage_alignment_confirmed,
    TRY_CAST(:raw_source_validation_confirmed AS INT) AS raw_source_validation_confirmed,
    TRY_CAST(:agent_trace_executed_confirmed AS INT) AS agent_trace_executed_confirmed,
    TRY_CAST(:agent_scope_alignment_confirmed AS INT) AS agent_scope_alignment_confirmed,
    TRY_CAST(:agent_unsafe_aggregation_confirmed AS INT) AS agent_unsafe_aggregation_confirmed
),
runtime_inputs AS (
  SELECT *,
    TRY_CAST(NULLIF(agent_answer_text, '') AS DECIMAL(38,5)) AS agent_answer_value,
    TRY_CAST(NULLIF(independent_raw_reference_text, '') AS DECIMAL(38,5))
      AS independent_raw_reference_total,
    CASE WHEN agent_answer_text IS NULL OR agent_answer_text = '' THEN 'NOT_PROVIDED'
         WHEN TRY_CAST(agent_answer_text AS DECIMAL(38,5)) IS NULL THEN 'INVALID_NUMBER'
         ELSE 'PASS' END AS agent_answer_parse_status,
    CASE WHEN independent_raw_reference_text IS NULL OR independent_raw_reference_text = '' THEN 'NOT_PROVIDED'
         WHEN TRY_CAST(independent_raw_reference_text AS DECIMAL(38,5)) IS NULL THEN 'INVALID_NUMBER'
         ELSE 'PASS' END AS raw_reference_parse_status
  FROM runtime_raw_inputs
),
runtime_control AS (
  SELECT *,
    CASE WHEN agent_answer_parse_status <> 'INVALID_NUMBER'
           AND raw_reference_parse_status <> 'INVALID_NUMBER'
           AND identity_rule_confirmed IN (0,1)
           AND metric_rule_confirmed IN (0,1)
           AND lineage_alignment_confirmed IN (0,1)
           AND raw_source_validation_confirmed IN (0,1)
           AND agent_trace_executed_confirmed IN (0,1)
           AND agent_scope_alignment_confirmed IN (0,1)
           AND agent_unsafe_aggregation_confirmed IN (0,1)
         THEN 'PASS' ELSE 'BLOCKED_INVALID_RUNTIME_INPUT' END AS control_status
  FROM runtime_inputs
),
gold_source AS (
  SELECT *
  FROM `dev`.`sales_ai_assistant_gold`.`csm_csal_summary` VERSION AS OF :gold_version
  WHERE month = :report_month
),
upstream_source AS (
  SELECT *
  FROM `dev`.`crmi_gold`.`csal_teu_performance` VERSION AS OF :upstream_version
),
upstream_snapshot_summary AS (
  SELECT
    COUNT(DISTINCT run_date) AS upstream_distinct_run_dates,
    SUM(CASE WHEN run_date IS NULL THEN 1 ELSE 0 END) AS upstream_null_run_date_rows,
    MIN(run_date) AS upstream_minimum_run_date,
    MAX(run_date) AS upstream_maximum_run_date
  FROM upstream_source
  WHERE month = :report_month
),
gold_long_raw AS (
  SELECT
    m.*,
    g.month, g.week_num, g.customer, g.sales_rep, g.agreement, g.tcr, g.service,
    CASE m.evidence_id
      WHEN 'E01' THEN CAST(g.monthly_booked_teu AS STRING)
      WHEN 'E02' THEN CAST(g.monthly_cancelled_teu AS STRING)
      WHEN 'E03' THEN CAST(g.monthly_rejected_teu AS STRING)
      WHEN 'E04' THEN CAST(g.monthly_confirmed_teu AS STRING)
      WHEN 'E05' THEN CAST(g.booked_teu AS STRING)
      WHEN 'E06' THEN CAST(g.confirmed_teu AS STRING)
      WHEN 'E07' THEN CAST(g.cancelled_teu AS STRING)
      WHEN 'E08' THEN CAST(g.rejected_teu AS STRING)
      WHEN 'E09' THEN CAST(g.no_show_teu AS STRING)
      WHEN 'E10' THEN CAST(g.terminated_teu AS STRING)
    END AS raw_metric_text
  FROM gold_source g CROSS JOIN metric_catalog m
),
gold_long AS (
  SELECT *,
    TRY_CAST(raw_metric_text AS DECIMAL(38,5)) AS metric_value,
    CASE WHEN raw_metric_text IS NOT NULL
           AND TRY_CAST(raw_metric_text AS DECIMAL(38,5)) IS NULL THEN 1 ELSE 0 END AS invalid_numeric
  FROM gold_long_raw
),
gold_raw_totals AS (
  SELECT evidence_id,
    COUNT(*) AS gold_physical_rows,
    SUM(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS gold_null_metric_rows,
    SUM(invalid_numeric) AS gold_invalid_numeric_rows,
    SUM(metric_value) AS gold_raw_visible_sum
  FROM gold_long
  GROUP BY evidence_id
),
gold_monthly_group_stats AS (
  SELECT evidence_id, month, customer, sales_rep, agreement, service,
    COUNT(*) AS physical_rows,
    COUNT(DISTINCT metric_value)
      + MAX(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS observed_metric_states,
    SUM(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS null_metric_rows,
    SUM(invalid_numeric) AS invalid_numeric_rows,
    MAX(CASE WHEN COALESCE(TRIM(CAST(month AS STRING)), '') = ''
               OR COALESCE(TRIM(customer), '') = ''
               OR COALESCE(TRIM(sales_rep), '') = ''
               OR COALESCE(TRIM(agreement), '') = ''
               OR COALESCE(TRIM(service), '') = '' THEN 1 ELSE 0 END) AS has_missing_key,
    MIN(metric_value) AS sole_value
  FROM gold_long
  WHERE evidence_scope = 'MONTHLY'
  GROUP BY evidence_id, month, customer, sales_rep, agreement, service
),
gold_booking_group_stats AS (
  SELECT evidence_id, month, customer, agreement, week_num, service, tcr,
    COUNT(*) AS physical_rows,
    COUNT(DISTINCT metric_value)
      + MAX(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS observed_metric_states,
    SUM(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS null_metric_rows,
    SUM(invalid_numeric) AS invalid_numeric_rows,
    MAX(CASE WHEN COALESCE(TRIM(CAST(month AS STRING)), '') = ''
               OR COALESCE(TRIM(customer), '') = ''
               OR COALESCE(TRIM(agreement), '') = ''
               OR COALESCE(TRIM(week_num), '') = ''
               OR COALESCE(TRIM(service), '') = ''
               OR COALESCE(TRIM(tcr), '') = '' THEN 1 ELSE 0 END) AS has_missing_key,
    MIN(metric_value) AS sole_value
  FROM gold_long
  WHERE evidence_scope = 'BOOKING'
  GROUP BY evidence_id, month, customer, agreement, week_num, service, tcr
),
gold_group_stats AS (
  SELECT evidence_id, physical_rows, observed_metric_states, null_metric_rows,
         invalid_numeric_rows, has_missing_key, sole_value
  FROM gold_monthly_group_stats
  UNION ALL
  SELECT evidence_id, physical_rows, observed_metric_states, null_metric_rows,
         invalid_numeric_rows, has_missing_key, sole_value
  FROM gold_booking_group_stats
),
gold_group_eval AS (
  SELECT *,
    CASE WHEN has_missing_key = 0 AND null_metric_rows = 0
               AND invalid_numeric_rows = 0 AND observed_metric_states = 1
         THEN sole_value END AS guarded_group_value,
    CASE WHEN has_missing_key > 0 THEN 'BLOCKED_MISSING_KEY'
         WHEN invalid_numeric_rows > 0 THEN 'BLOCKED_INVALID_NUMBER'
         WHEN null_metric_rows > 0 THEN 'BLOCKED_NULL_METRIC'
         WHEN observed_metric_states > 1 THEN 'BLOCKED_CONFLICT'
         ELSE 'CONSISTENT_CANDIDATE' END AS group_status
  FROM gold_group_stats
),
gold_candidate_totals AS (
  SELECT evidence_id,
    COUNT(*) AS gold_candidate_groups,
    SUM(CASE WHEN physical_rows > 1 THEN 1 ELSE 0 END) AS gold_repeated_groups,
    SUM(GREATEST(physical_rows - 1, 0)) AS gold_extra_physical_rows,
    SUM(CASE WHEN group_status <> 'CONSISTENT_CANDIDATE' THEN 1 ELSE 0 END) AS gold_blocked_groups,
    SUM(CASE WHEN group_status = 'CONSISTENT_CANDIDATE' THEN guarded_group_value ELSE 0 END)
      AS gold_eligible_subtotal,
    SUM(CASE WHEN group_status = 'CONSISTENT_CANDIDATE'
             THEN GREATEST(physical_rows - 1, 0) * guarded_group_value ELSE 0 END)
      AS gold_repetition_effect,
    CASE WHEN SUM(CASE WHEN group_status <> 'CONSISTENT_CANDIDATE' THEN 1 ELSE 0 END) = 0
         THEN SUM(guarded_group_value) END AS gold_candidate_total
  FROM gold_group_eval
  GROUP BY evidence_id
),
upstream_long_raw AS (
  SELECT
    m.*,
    u.month, u.week_num, u.customer, u.sales AS sales_rep, u.agreement, u.tcr, u.service,
    u.booking_number, u.booking_status,
    CASE m.upstream_metric
      WHEN 'booked_teu' THEN CAST(u.booked_teu AS STRING)
      WHEN 'confirmed_teu' THEN CAST(u.confirmed_teu AS STRING)
      WHEN 'cancelled_teu' THEN CAST(u.cancelled_teu AS STRING)
      WHEN 'rejected_teu' THEN CAST(u.rejected_teu AS STRING)
      WHEN 'no_show_teu' THEN CAST(u.no_show_teu AS STRING)
      WHEN 'terminated_teu' THEN CAST(u.terminated_teu AS STRING)
    END AS raw_metric_text
  FROM upstream_source u CROSS JOIN metric_catalog m
),
upstream_long AS (
  SELECT *,
    TRY_CAST(raw_metric_text AS DECIMAL(38,5)) AS metric_value,
    CASE WHEN raw_metric_text IS NOT NULL
           AND TRY_CAST(raw_metric_text AS DECIMAL(38,5)) IS NULL THEN 1 ELSE 0 END AS invalid_numeric,
    CASE WHEN TRY_CAST(raw_metric_text AS DECIMAL(38,5)) IS NOT NULL
           AND TRY_CAST(raw_metric_text AS DECIMAL(38,5))
               <> FLOOR(TRY_CAST(raw_metric_text AS DECIMAL(38,5)))
         THEN 1 ELSE 0 END AS fractional_numeric,
    CASE WHEN TRY_CAST(raw_metric_text AS DECIMAL(38,5)) > 2147483647
           OR TRY_CAST(raw_metric_text AS DECIMAL(38,5)) < -2147483648
         THEN 1 ELSE 0 END AS outside_int_range
  FROM upstream_long_raw
),
-- Saved-logic replay: omit month and use MAX at booking/status grain, as the retained source does.
-- This is not labelled an exact deployed replay until code and version lineage are confirmed.
producer_status_stats AS (
  SELECT evidence_id, customer, agreement, week_num, service, tcr, booking_number, booking_status,
    COUNT(*) AS physical_rows,
    COUNT(DISTINCT month) + MAX(CASE WHEN month IS NULL THEN 1 ELSE 0 END) AS month_states,
    SUM(CASE WHEN month = :report_month THEN 1 ELSE 0 END) AS report_month_rows,
    SUM(CASE WHEN month IS NULL OR month <> :report_month THEN 1 ELSE 0 END) AS nonreport_month_rows,
    COUNT(DISTINCT metric_value)
      + MAX(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS observed_metric_states,
    SUM(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS null_metric_rows,
    SUM(invalid_numeric) AS invalid_numeric_rows,
    SUM(fractional_numeric) AS fractional_numeric_rows,
    SUM(outside_int_range) AS outside_int_range_rows,
    MAX(CASE WHEN COALESCE(TRIM(customer), '') = ''
               OR COALESCE(TRIM(agreement), '') = ''
               OR COALESCE(TRIM(week_num), '') = ''
               OR COALESCE(TRIM(service), '') = ''
               OR COALESCE(TRIM(tcr), '') = ''
               OR COALESCE(TRIM(booking_number), '') = ''
               OR COALESCE(TRIM(booking_status), '') = '' THEN 1 ELSE 0 END) AS has_missing_key,
    TRY_CAST(MAX(metric_value) AS INT) AS producer_max_value
  FROM upstream_long
  GROUP BY evidence_id, customer, agreement, week_num, service, tcr, booking_number, booking_status
),
producer_booking_agg AS (
  SELECT evidence_id, customer, agreement, week_num, service, tcr,
    TRY_CAST(SUM(producer_max_value) AS INT) AS producer_booking_value,
    SUM(CASE WHEN observed_metric_states > 1 THEN 1 ELSE 0 END) AS hidden_conflict_groups,
    SUM(CASE WHEN null_metric_rows > 0 THEN 1 ELSE 0 END) AS max_ignored_null_groups,
    SUM(CASE WHEN invalid_numeric_rows > 0 THEN 1 ELSE 0 END) AS invalid_numeric_groups,
    SUM(CASE WHEN fractional_numeric_rows > 0 THEN 1 ELSE 0 END) AS fractional_numeric_groups,
    SUM(CASE WHEN outside_int_range_rows > 0 THEN 1 ELSE 0 END) AS outside_int_range_groups,
    CASE WHEN SUM(producer_max_value) > 2147483647
           OR SUM(producer_max_value) < -2147483648 THEN 1 ELSE 0 END
      AS aggregate_outside_int_range,
    SUM(CASE WHEN has_missing_key > 0 THEN 1 ELSE 0 END) AS missing_key_groups,
    SUM(CASE WHEN month_states > 1 THEN 1 ELSE 0 END) AS cross_month_status_groups,
    SUM(CASE WHEN nonreport_month_rows > 0 THEN 1 ELSE 0 END) AS nonreport_month_status_groups
  FROM producer_status_stats
  GROUP BY evidence_id, customer, agreement, week_num, service, tcr
),
report_allocation_keys AS (
  SELECT DISTINCT month, week_num, customer, sales AS sales_rep, agreement, tcr, service, category
  FROM upstream_source
  WHERE month = :report_month
),
report_booking_keys AS (
  SELECT DISTINCT customer, agreement, week_num, service, tcr
  FROM report_allocation_keys
),
producer_booking_report AS (
  SELECT p.*
  FROM producer_booking_agg p
  INNER JOIN report_booking_keys r
    ON r.customer = p.customer AND r.agreement = p.agreement
   AND r.week_num = p.week_num AND r.service = p.service AND r.tcr = p.tcr
),
producer_monthly_groups AS (
  SELECT m.evidence_id, a.month, a.customer, a.sales_rep, a.agreement, a.service,
    TRY_CAST(SUM(p.producer_booking_value) AS INT) AS producer_monthly_value,
    COALESCE(SUM(p.hidden_conflict_groups), 0) AS hidden_conflict_groups,
    COALESCE(SUM(p.max_ignored_null_groups), 0) AS max_ignored_null_groups,
    COALESCE(SUM(p.invalid_numeric_groups), 0) AS invalid_numeric_groups,
    COALESCE(SUM(p.fractional_numeric_groups), 0) AS fractional_numeric_groups,
    COALESCE(SUM(p.outside_int_range_groups), 0) AS outside_int_range_groups,
    COALESCE(SUM(p.aggregate_outside_int_range), 0)
      + CASE WHEN SUM(p.producer_booking_value) > 2147483647
               OR SUM(p.producer_booking_value) < -2147483648 THEN 1 ELSE 0 END
      AS aggregate_outside_int_range_groups,
    COALESCE(SUM(p.missing_key_groups), 0) AS missing_key_groups,
    COALESCE(SUM(p.cross_month_status_groups), 0) AS cross_month_status_groups,
    COALESCE(SUM(p.nonreport_month_status_groups), 0) AS nonreport_month_status_groups,
    SUM(CASE WHEN p.evidence_id IS NULL THEN 1 ELSE 0 END) AS unmatched_allocation_rows,
    MAX(CASE WHEN a.month IS NULL OR a.customer IS NULL OR a.sales_rep IS NULL
               OR a.agreement IS NULL OR a.service IS NULL THEN 1 ELSE 0 END)
      AS unsurfaced_by_final_equality,
    MAX(CASE WHEN TRIM(COALESCE(a.month, '')) = '' OR TRIM(COALESCE(a.customer, '')) = ''
               OR TRIM(COALESCE(a.sales_rep, '')) = '' OR TRIM(COALESCE(a.agreement, '')) = ''
               OR TRIM(COALESCE(a.service, '')) = '' THEN 1 ELSE 0 END)
      AS monthly_blank_or_null_key_group
  FROM report_allocation_keys a
  CROSS JOIN (
    SELECT evidence_id FROM metric_catalog WHERE evidence_scope = 'MONTHLY'
  ) m
  LEFT JOIN producer_booking_agg p
    ON p.evidence_id = m.evidence_id
   AND p.customer = a.customer AND p.agreement = a.agreement
   AND p.week_num = a.week_num AND p.service = a.service AND p.tcr = a.tcr
  GROUP BY m.evidence_id, a.month, a.customer, a.sales_rep, a.agreement, a.service
),
producer_replay_totals AS (
  SELECT evidence_id,
    COUNT(*) AS producer_replay_groups,
    SUM(hidden_conflict_groups) AS producer_hidden_conflict_groups,
    SUM(max_ignored_null_groups) AS producer_max_ignored_null_groups,
    SUM(invalid_numeric_groups) AS producer_invalid_numeric_groups,
    SUM(fractional_numeric_groups) AS producer_fractional_numeric_groups,
    SUM(outside_int_range_groups) AS producer_outside_int_range_groups,
    SUM(aggregate_outside_int_range) AS producer_aggregate_outside_int_range_groups,
    SUM(missing_key_groups) AS producer_missing_key_groups,
    SUM(cross_month_status_groups) AS producer_cross_month_status_groups,
    SUM(nonreport_month_status_groups) AS producer_nonreport_month_status_groups,
    0 AS producer_unmatched_allocation_rows,
    0 AS producer_unsurfaced_monthly_groups,
    0 AS producer_monthly_blank_or_null_key_groups,
    SUM(producer_booking_value) AS upstream_producer_replay_total
  FROM producer_booking_report
  WHERE evidence_id IN ('E05','E06','E07','E08','E09','E10')
  GROUP BY evidence_id
  UNION ALL
  SELECT evidence_id,
    COUNT(*) AS producer_replay_groups,
    SUM(hidden_conflict_groups), SUM(max_ignored_null_groups), SUM(invalid_numeric_groups),
    SUM(fractional_numeric_groups), SUM(outside_int_range_groups),
    SUM(aggregate_outside_int_range_groups),
    SUM(missing_key_groups), SUM(cross_month_status_groups),
    SUM(nonreport_month_status_groups),
    SUM(unmatched_allocation_rows) AS producer_unmatched_allocation_rows,
    SUM(unsurfaced_by_final_equality) AS producer_unsurfaced_monthly_groups,
    SUM(monthly_blank_or_null_key_group) AS producer_monthly_blank_or_null_key_groups,
    SUM(CASE WHEN unsurfaced_by_final_equality = 0 THEN producer_monthly_value END)
      AS upstream_producer_replay_total
  FROM producer_monthly_groups
  WHERE evidence_id IN ('E01','E02','E03','E04')
  GROUP BY evidence_id
),
-- Guarded upstream calculation: add the selected month and reject, rather than hide, conflicts or gaps.
guarded_status_stats AS (
  SELECT evidence_id, month, customer, agreement, week_num, service, tcr, booking_number, booking_status,
    COUNT(*) AS physical_rows,
    COUNT(DISTINCT metric_value)
      + MAX(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS observed_metric_states,
    SUM(CASE WHEN metric_value IS NULL THEN 1 ELSE 0 END) AS null_metric_rows,
    SUM(invalid_numeric) AS invalid_numeric_rows,
    SUM(fractional_numeric) AS fractional_numeric_rows,
    SUM(outside_int_range) AS outside_int_range_rows,
    MAX(CASE WHEN COALESCE(TRIM(month), '') = '' OR COALESCE(TRIM(customer), '') = ''
               OR COALESCE(TRIM(agreement), '') = '' OR COALESCE(TRIM(week_num), '') = ''
               OR COALESCE(TRIM(service), '') = '' OR COALESCE(TRIM(tcr), '') = ''
               OR COALESCE(TRIM(booking_number), '') = ''
               OR COALESCE(TRIM(booking_status), '') = '' THEN 1 ELSE 0 END) AS has_missing_key,
    MIN(metric_value) AS sole_value
  FROM upstream_long
  WHERE month = :report_month
  GROUP BY evidence_id, month, customer, agreement, week_num, service, tcr, booking_number, booking_status
),
guarded_status_eval AS (
  SELECT *,
    CASE WHEN has_missing_key = 0 AND null_metric_rows = 0
               AND invalid_numeric_rows = 0 AND fractional_numeric_rows = 0
               AND outside_int_range_rows = 0 AND observed_metric_states = 1
         THEN sole_value END AS guarded_status_value,
    CASE WHEN has_missing_key > 0 THEN 'BLOCKED_MISSING_KEY'
         WHEN invalid_numeric_rows > 0 THEN 'BLOCKED_INVALID_NUMBER'
         WHEN outside_int_range_rows > 0 THEN 'BLOCKED_OUTSIDE_INT_RANGE'
         WHEN fractional_numeric_rows > 0 THEN 'BLOCKED_FRACTIONAL_VALUE'
         WHEN null_metric_rows > 0 THEN 'BLOCKED_NULL_METRIC'
         WHEN observed_metric_states > 1 THEN 'BLOCKED_CONFLICT'
         ELSE 'CONSISTENT_CANDIDATE' END AS group_status
  FROM guarded_status_stats
),
guarded_upstream_totals AS (
  SELECT evidence_id,
    COUNT(*) AS guarded_upstream_groups,
    SUM(CASE WHEN physical_rows > 1 THEN 1 ELSE 0 END) AS guarded_repeated_groups,
    SUM(CASE WHEN group_status <> 'CONSISTENT_CANDIDATE' THEN 1 ELSE 0 END)
      AS guarded_blocked_groups,
    SUM(CASE WHEN group_status = 'CONSISTENT_CANDIDATE' THEN guarded_status_value ELSE 0 END)
      AS guarded_eligible_subtotal,
    CASE WHEN SUM(CASE WHEN group_status <> 'CONSISTENT_CANDIDATE' THEN 1 ELSE 0 END) = 0
         THEN SUM(guarded_status_value) END AS guarded_upstream_total
  FROM guarded_status_eval
  GROUP BY evidence_id
),
sales_attribution AS (
  SELECT customer, agreement, week_num, service, tcr,
    COUNT(DISTINCT sales) + MAX(CASE WHEN sales IS NULL THEN 1 ELSE 0 END) AS sales_rep_states
  FROM upstream_source
  WHERE month = :report_month
  GROUP BY customer, agreement, week_num, service, tcr
),
sales_attribution_summary AS (
  SELECT SUM(CASE WHEN sales_rep_states > 1 THEN 1 ELSE 0 END)
    AS booking_keys_with_multiple_sales_reps
  FROM sales_attribution
),
final_comparison AS (
  SELECT
    m.evidence_id, m.evidence_scope, m.production_question, m.gold_metric, m.upstream_metric,
    :report_month AS report_month, :gold_version AS gold_version, :upstream_version AS upstream_version,
    i.control_status, i.agent_answer_value, i.independent_raw_reference_total,
    z.upstream_distinct_run_dates, z.upstream_null_run_date_rows,
    z.upstream_minimum_run_date, z.upstream_maximum_run_date,
    r.gold_physical_rows, r.gold_null_metric_rows, r.gold_invalid_numeric_rows,
    r.gold_raw_visible_sum,
    CASE WHEN r.gold_physical_rows IS NULL OR r.gold_physical_rows = 0 THEN 'EMPTY_SCOPE'
         WHEN r.gold_invalid_numeric_rows > 0 THEN 'BLOCKED_INVALID_NUMBER'
         WHEN r.gold_null_metric_rows > 0 THEN 'PARTIAL_SUM_NULLS_PRESENT'
         ELSE 'COMPLETE_RAW_SUM' END AS gold_raw_status,
    c.gold_candidate_groups, c.gold_repeated_groups, c.gold_extra_physical_rows,
    c.gold_blocked_groups, c.gold_eligible_subtotal, c.gold_repetition_effect,
    c.gold_candidate_total,
    CASE WHEN c.gold_candidate_groups IS NULL OR c.gold_candidate_groups = 0 THEN 'EMPTY_SCOPE'
         WHEN c.gold_blocked_groups > 0 THEN 'BLOCKED_KEYS_VALUES_OR_CONFLICTS'
         ELSE 'CONSISTENT_CANDIDATE_NOT_BUSINESS_VALIDATED' END AS gold_candidate_status,
    p.producer_replay_groups, p.producer_hidden_conflict_groups,
    p.producer_max_ignored_null_groups, p.producer_invalid_numeric_groups,
    p.producer_fractional_numeric_groups, p.producer_outside_int_range_groups,
    p.producer_aggregate_outside_int_range_groups,
    p.producer_missing_key_groups, p.producer_cross_month_status_groups,
    p.producer_nonreport_month_status_groups,
    p.producer_unmatched_allocation_rows, p.producer_unsurfaced_monthly_groups,
    p.producer_monthly_blank_or_null_key_groups,
    p.upstream_producer_replay_total,
    CASE WHEN p.producer_replay_groups IS NULL OR p.producer_replay_groups = 0 THEN 'EMPTY_OR_UNMATCHED_SCOPE'
         WHEN p.producer_hidden_conflict_groups > 0 OR p.producer_invalid_numeric_groups > 0
           THEN 'PRODUCER_MAX_MASKED_CONFLICT_OR_INVALID_VALUE'
         WHEN p.producer_fractional_numeric_groups > 0 OR p.producer_outside_int_range_groups > 0
           OR p.producer_aggregate_outside_int_range_groups > 0
           THEN 'SAVED_LOGIC_CAST_CHANGES_OR_REJECTS_VALUES'
         WHEN p.producer_max_ignored_null_groups > 0 OR p.producer_missing_key_groups > 0
           OR p.producer_cross_month_status_groups > 0
           OR p.producer_nonreport_month_status_groups > 0
           OR p.producer_unmatched_allocation_rows > 0
           OR p.producer_unsurfaced_monthly_groups > 0
           OR p.producer_monthly_blank_or_null_key_groups > 0
           THEN 'PRODUCER_REPLAY_HAS_VISIBLE_LIMITATIONS'
         ELSE 'SAVED_PRODUCER_LOGIC_REPLAY_CANDIDATE' END AS producer_replay_status,
    u.guarded_upstream_groups, u.guarded_repeated_groups, u.guarded_blocked_groups,
    u.guarded_eligible_subtotal, u.guarded_upstream_total,
    CASE WHEN u.guarded_upstream_groups IS NULL OR u.guarded_upstream_groups = 0 THEN 'EMPTY_SCOPE'
         WHEN u.guarded_blocked_groups > 0 THEN 'BLOCKED_KEYS_VALUES_OR_CONFLICTS'
         ELSE 'TECHNICALLY_CONSISTENT_NOT_BUSINESS_VALIDATED' END AS guarded_upstream_status,
    s.booking_keys_with_multiple_sales_reps,
    r.gold_raw_visible_sum - u.guarded_upstream_total AS raw_gold_minus_guarded_upstream,
    c.gold_candidate_total - u.guarded_upstream_total AS gold_candidate_minus_guarded_upstream,
    p.upstream_producer_replay_total - u.guarded_upstream_total AS producer_replay_minus_guarded,
    CASE WHEN r.gold_physical_rows IS NULL OR r.gold_physical_rows = 0
           OR c.gold_candidate_groups IS NULL OR c.gold_candidate_groups = 0
           OR u.guarded_upstream_groups IS NULL OR u.guarded_upstream_groups = 0
           THEN 'UNRESOLVED_EMPTY_SCOPE'
         WHEN z.upstream_distinct_run_dates <> 1 OR z.upstream_null_run_date_rows > 0
           THEN 'UNRESOLVED_MULTIPLE_OR_MISSING_UPSTREAM_RUN_DATES'
         WHEN c.gold_blocked_groups > 0 OR u.guarded_blocked_groups > 0
           THEN 'UNRESOLVED_BLOCKED_POPULATION'
         WHEN p.producer_hidden_conflict_groups > 0 OR p.producer_invalid_numeric_groups > 0
           OR p.producer_fractional_numeric_groups > 0 OR p.producer_outside_int_range_groups > 0
           OR p.producer_aggregate_outside_int_range_groups > 0
           OR p.producer_max_ignored_null_groups > 0 OR p.producer_missing_key_groups > 0
           OR p.producer_cross_month_status_groups > 0
           OR p.producer_nonreport_month_status_groups > 0
           OR p.producer_unmatched_allocation_rows > 0
           OR p.producer_unsurfaced_monthly_groups > 0
           OR p.producer_monthly_blank_or_null_key_groups > 0
           THEN 'UNRESOLVED_SAVED_PRODUCER_LIMITATION'
         WHEN m.evidence_scope = 'MONTHLY'
           AND c.gold_candidate_total = p.upstream_producer_replay_total
           AND p.upstream_producer_replay_total <> u.guarded_upstream_total
           AND r.gold_raw_visible_sum <> c.gold_candidate_total
           AND r.gold_raw_visible_sum - c.gold_candidate_total = c.gold_repetition_effect
           THEN 'MONTHLY_PRODUCER_FANOUT_AND_FINAL_ROW_REPETITION_OBSERVED'
         WHEN m.evidence_scope = 'MONTHLY'
           AND c.gold_candidate_total = p.upstream_producer_replay_total
           AND p.upstream_producer_replay_total <> u.guarded_upstream_total
           AND r.gold_raw_visible_sum = c.gold_candidate_total
           THEN 'MONTHLY_PRODUCER_FANOUT_OBSERVED'
         WHEN c.gold_candidate_total = u.guarded_upstream_total
           AND p.upstream_producer_replay_total = u.guarded_upstream_total
           AND r.gold_raw_visible_sum <> u.guarded_upstream_total
           AND r.gold_raw_visible_sum - c.gold_candidate_total = c.gold_repetition_effect
           THEN 'FINAL_GOLD_ROW_REPETITION_OBSERVED'
         WHEN r.gold_raw_visible_sum = u.guarded_upstream_total
           AND c.gold_candidate_total = u.guarded_upstream_total
           AND p.upstream_producer_replay_total = u.guarded_upstream_total
           THEN 'NO_GRAIN_EFFECT_OBSERVED'
         ELSE 'RECONCILIATION_DIFFERENCE_REQUIRES_REVIEW' END AS technical_result,
    CASE WHEN i.control_status <> 'PASS' THEN i.control_status
         WHEN i.identity_rule_confirmed <> 1 THEN 'PENDING_AUTHORITATIVE_IDENTITY_RULE'
         WHEN i.metric_rule_confirmed <> 1 THEN 'PENDING_APPROVED_METRIC_RULE'
         WHEN i.lineage_alignment_confirmed <> 1 THEN 'PENDING_VERSION_LINEAGE_ALIGNMENT'
         WHEN m.evidence_scope = 'MONTHLY' AND s.booking_keys_with_multiple_sales_reps > 0
           THEN 'PENDING_MONTHLY_SALES_ATTRIBUTION_RULE'
         ELSE 'READY_FOR_BUSINESS_REVIEW' END AS business_validation_status,
    i.agent_answer_parse_status,
    i.raw_reference_parse_status,
    i.identity_rule_confirmed,
    i.metric_rule_confirmed,
    i.lineage_alignment_confirmed,
    i.raw_source_validation_confirmed,
    i.agent_trace_executed_confirmed,
    i.agent_scope_alignment_confirmed,
    i.agent_unsafe_aggregation_confirmed
  FROM metric_catalog m
  LEFT JOIN gold_raw_totals r USING (evidence_id)
  LEFT JOIN gold_candidate_totals c USING (evidence_id)
  LEFT JOIN producer_replay_totals p USING (evidence_id)
  LEFT JOIN guarded_upstream_totals u USING (evidence_id)
  CROSS JOIN sales_attribution_summary s
  CROSS JOIN upstream_snapshot_summary z
  CROSS JOIN runtime_control i
),
attributed_comparison AS (
  SELECT f.*,
    CASE
      WHEN f.control_status <> 'PASS'
        THEN f.control_status
      WHEN UPPER(:evidence_id) = 'ALL'
        THEN 'PENDING_SELECT_ONE_EVIDENCE_ID_FOR_AGENT_ATTRIBUTION'
      WHEN f.agent_answer_value IS NULL
        THEN 'PENDING_FRESH_AGENT_ANSWER'
      WHEN f.independent_raw_reference_total IS NULL
        THEN 'UNRESOLVED_NO_INDEPENDENT_RAW_REFERENCE'
      WHEN f.agent_trace_executed_confirmed <> 1
        THEN 'PENDING_EXECUTED_AGENT_SQL_OR_TOOL_TRACE'
      WHEN f.agent_scope_alignment_confirmed <> 1
        THEN 'PENDING_AGENT_SOURCE_FILTER_AND_VERSION_ALIGNMENT'
      WHEN f.lineage_alignment_confirmed <> 1
        THEN 'PENDING_VERSION_LINEAGE_ALIGNMENT'
      WHEN f.raw_source_validation_confirmed <> 1
        THEN 'TECHNICAL_GRAIN_PATTERN_ONLY_RAW_BUSINESS_TRUTH_NOT_CONFIRMED'
      WHEN f.identity_rule_confirmed <> 1
        THEN 'PENDING_AUTHORITATIVE_IDENTITY_RULE'
      WHEN f.metric_rule_confirmed <> 1
        THEN 'PENDING_APPROVED_METRIC_RULE'
      WHEN f.evidence_scope = 'MONTHLY' AND f.booking_keys_with_multiple_sales_reps > 0
        THEN 'PENDING_MONTHLY_SALES_ATTRIBUTION_RULE'
      WHEN f.gold_physical_rows IS NULL OR f.gold_physical_rows = 0
        OR f.gold_candidate_groups IS NULL OR f.gold_candidate_groups = 0
        OR f.guarded_upstream_groups IS NULL OR f.guarded_upstream_groups = 0
        THEN 'UNRESOLVED_EMPTY_SCOPE'
      WHEN f.gold_blocked_groups > 0 OR f.guarded_blocked_groups > 0
        THEN 'UNRESOLVED_BLOCKED_POPULATION'
      WHEN f.upstream_distinct_run_dates <> 1 OR f.upstream_null_run_date_rows > 0
        THEN 'UNRESOLVED_MULTIPLE_OR_MISSING_UPSTREAM_RUN_DATES'
      WHEN f.producer_hidden_conflict_groups > 0 OR f.producer_invalid_numeric_groups > 0
        OR f.producer_fractional_numeric_groups > 0 OR f.producer_outside_int_range_groups > 0
        OR f.producer_aggregate_outside_int_range_groups > 0
        OR f.producer_max_ignored_null_groups > 0 OR f.producer_missing_key_groups > 0
        OR f.producer_cross_month_status_groups > 0
        OR f.producer_nonreport_month_status_groups > 0
        OR f.producer_unmatched_allocation_rows > 0
        OR f.producer_unsurfaced_monthly_groups > 0
        OR f.producer_monthly_blank_or_null_key_groups > 0
        THEN 'UNRESOLVED_SAVED_PRODUCER_LIMITATION'
      WHEN f.agent_answer_value = f.independent_raw_reference_total
        THEN 'AGENT_ANSWER_CONFIRMED_CORRECT_FOR_ALIGNED_REFERENCE'
      WHEN f.agent_unsafe_aggregation_confirmed <> 1
        THEN 'AGENT_ANSWER_DIFFERS_CAUSE_NOT_PROVEN'
      WHEN f.agent_answer_value <> f.independent_raw_reference_total
        AND f.technical_result IN (
          'FINAL_GOLD_ROW_REPETITION_OBSERVED',
          'MONTHLY_PRODUCER_FANOUT_OBSERVED',
          'MONTHLY_PRODUCER_FANOUT_AND_FINAL_ROW_REPETITION_OBSERVED'
        )
        AND f.agent_answer_value = f.gold_raw_visible_sum
        AND f.independent_raw_reference_total = f.guarded_upstream_total
        AND f.gold_raw_visible_sum <> f.guarded_upstream_total
        AND f.gold_candidate_total = f.upstream_producer_replay_total
        AND f.gold_raw_visible_sum - f.gold_candidate_total = f.gold_repetition_effect
        AND (f.evidence_scope = 'MONTHLY'
             OR (f.gold_candidate_total = f.guarded_upstream_total
                 AND f.upstream_producer_replay_total = f.guarded_upstream_total))
        THEN 'AGENT_GRAIN_ERROR_SUPPORTED_BY_ALL_REQUIRED_GATES'
      WHEN f.agent_answer_value <> f.independent_raw_reference_total
        THEN 'AGENT_ANSWER_INCORRECT_FOR_ALIGNED_REFERENCE_CAUSE_UNPROVEN'
      ELSE 'AGENT_ERROR_NOT_ESTABLISHED'
    END AS agent_error_attribution
  FROM final_comparison f
)
SELECT
  evidence_id,
  evidence_scope,
  production_question,
  report_month,
  gold_version,
  upstream_version,
  control_status,
  agent_answer_parse_status,
  raw_reference_parse_status,
  agent_answer_value,
  independent_raw_reference_total,
  upstream_distinct_run_dates,
  upstream_null_run_date_rows,
  gold_physical_rows,
  gold_raw_visible_sum,
  gold_candidate_groups,
  gold_repeated_groups,
  gold_extra_physical_rows,
  gold_blocked_groups,
  gold_candidate_total,
  gold_repetition_effect,
  upstream_producer_replay_total,
  producer_replay_status,
  CONCAT(
    'hidden_conflicts=', COALESCE(CAST(producer_hidden_conflict_groups AS STRING), 'NULL'),
    ', ignored_nulls=', COALESCE(CAST(producer_max_ignored_null_groups AS STRING), 'NULL'),
    ', invalid_numbers=', COALESCE(CAST(producer_invalid_numeric_groups AS STRING), 'NULL'),
    ', fractional_values=', COALESCE(CAST(producer_fractional_numeric_groups AS STRING), 'NULL'),
    ', int_range=', COALESCE(CAST(producer_outside_int_range_groups AS STRING), 'NULL'),
    ', aggregate_int_range=', COALESCE(CAST(producer_aggregate_outside_int_range_groups AS STRING), 'NULL'),
    ', missing_keys=', COALESCE(CAST(producer_missing_key_groups AS STRING), 'NULL'),
    ', cross_month=', COALESCE(CAST(producer_cross_month_status_groups AS STRING), 'NULL'),
    ', nonreport_month=', COALESCE(CAST(producer_nonreport_month_status_groups AS STRING), 'NULL'),
    ', unmatched_allocations=', COALESCE(CAST(producer_unmatched_allocation_rows AS STRING), 'NULL'),
    ', unsurfaced_monthly=', COALESCE(CAST(producer_unsurfaced_monthly_groups AS STRING), 'NULL'),
    ', blank_or_null_monthly_keys=', COALESCE(CAST(producer_monthly_blank_or_null_key_groups AS STRING), 'NULL')
  ) AS producer_limit_counts,
  guarded_upstream_total,
  guarded_blocked_groups,
  guarded_upstream_status,
  raw_gold_minus_guarded_upstream,
  technical_result,
  business_validation_status,
  agent_error_attribution
FROM attributed_comparison
WHERE UPPER(:evidence_id) = 'ALL' OR evidence_id = UPPER(:evidence_id)
ORDER BY evidence_id;

-- COMMAND ----------
-- DBTITLE 1,6. Aggregate guarded-intermediate blockers without exposing customer rows
-- Run Cell 5 first. Then use its blocked counts to decide whether a business conclusion is possible.
-- This compact diagnostic repeats only the guarded upstream check and never selects identity values.
WITH metric_catalog AS (
  SELECT * FROM VALUES
    ('E01','booked_teu'), ('E02','cancelled_teu'), ('E03','rejected_teu'),
    ('E04','confirmed_teu'), ('E05','booked_teu'), ('E06','confirmed_teu'),
    ('E07','cancelled_teu'), ('E08','rejected_teu'), ('E09','no_show_teu'),
    ('E10','terminated_teu') AS t(evidence_id, upstream_metric)
), source AS (
  SELECT * FROM `dev`.`crmi_gold`.`csal_teu_performance` VERSION AS OF :upstream_version
  WHERE month = :report_month
), raw_long_form AS (
  SELECT m.evidence_id, s.month, s.customer, s.agreement, s.week_num, s.service, s.tcr,
         s.booking_number, s.booking_status,
    CASE m.upstream_metric
      WHEN 'booked_teu' THEN CAST(s.booked_teu AS STRING)
      WHEN 'confirmed_teu' THEN CAST(s.confirmed_teu AS STRING)
      WHEN 'cancelled_teu' THEN CAST(s.cancelled_teu AS STRING)
      WHEN 'rejected_teu' THEN CAST(s.rejected_teu AS STRING)
      WHEN 'no_show_teu' THEN CAST(s.no_show_teu AS STRING)
      WHEN 'terminated_teu' THEN CAST(s.terminated_teu AS STRING) END AS raw_metric_text
  FROM source s CROSS JOIN metric_catalog m
), long_form AS (
  SELECT *,
    TRY_CAST(raw_metric_text AS DECIMAL(38,5)) AS value,
    CASE WHEN raw_metric_text IS NOT NULL
           AND TRY_CAST(raw_metric_text AS DECIMAL(38,5)) IS NULL THEN 1 ELSE 0 END AS invalid_numeric,
    CASE WHEN TRY_CAST(raw_metric_text AS DECIMAL(38,5)) IS NOT NULL
           AND TRY_CAST(raw_metric_text AS DECIMAL(38,5))
               <> FLOOR(TRY_CAST(raw_metric_text AS DECIMAL(38,5))) THEN 1 ELSE 0 END
      AS fractional_numeric,
    CASE WHEN TRY_CAST(raw_metric_text AS DECIMAL(38,5)) > 2147483647
           OR TRY_CAST(raw_metric_text AS DECIMAL(38,5)) < -2147483648 THEN 1 ELSE 0 END
      AS outside_int_range
  FROM raw_long_form
), groups AS (
  SELECT evidence_id,
    COUNT(*) AS physical_rows,
    COUNT(DISTINCT value) + MAX(CASE WHEN value IS NULL THEN 1 ELSE 0 END) AS value_states,
    SUM(CASE WHEN raw_metric_text IS NULL THEN 1 ELSE 0 END) AS null_rows,
    SUM(invalid_numeric) AS invalid_numeric_rows,
    SUM(fractional_numeric) AS fractional_numeric_rows,
    SUM(outside_int_range) AS outside_int_range_rows,
    MAX(CASE WHEN COALESCE(TRIM(month), '') = '' OR COALESCE(TRIM(customer), '') = ''
               OR COALESCE(TRIM(agreement), '') = '' OR COALESCE(TRIM(week_num), '') = ''
               OR COALESCE(TRIM(service), '') = '' OR COALESCE(TRIM(tcr), '') = ''
               OR COALESCE(TRIM(booking_number), '') = ''
               OR COALESCE(TRIM(booking_status), '') = '' THEN 1 ELSE 0 END) AS missing_key
  FROM long_form
  GROUP BY evidence_id, month, customer, agreement, week_num, service, tcr, booking_number, booking_status
)
SELECT evidence_id,
  COUNT(*) AS groups_checked,
  SUM(CASE WHEN physical_rows > 1 THEN 1 ELSE 0 END) AS repeated_physical_groups,
  SUM(CASE WHEN value_states > 1 THEN 1 ELSE 0 END) AS conflicting_groups,
  SUM(CASE WHEN null_rows > 0 THEN 1 ELSE 0 END) AS groups_with_null_metric,
  SUM(CASE WHEN invalid_numeric_rows > 0 THEN 1 ELSE 0 END) AS groups_with_invalid_numeric,
  SUM(CASE WHEN fractional_numeric_rows > 0 THEN 1 ELSE 0 END) AS groups_with_fractional_values,
  SUM(CASE WHEN outside_int_range_rows > 0 THEN 1 ELSE 0 END) AS groups_outside_int_range,
  SUM(CASE WHEN missing_key > 0 THEN 1 ELSE 0 END) AS groups_with_missing_key
FROM groups
WHERE UPPER(:evidence_id) = 'ALL' OR evidence_id = UPPER(:evidence_id)
GROUP BY evidence_id
ORDER BY evidence_id;
