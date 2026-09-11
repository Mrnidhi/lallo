# Arm C Genie instructions

This is the Arm C personal test for the August 2026 CSM/CSAL comparison. Use only the attached personal dimensions and facts. Do not use production tables, other schemas, functions or external sources.

Choose one fact that matches the question:

- Allocation and swap questions use `fact_allocation_poc_v3_v80_aug2026`.
- Booking questions use `fact_booking_poc_v3_v80_aug2026`.
- Commitment questions use `fact_commitment_poc_v3_v80_aug2026`.
- Monthly performance questions use `fact_monthly_performance_poc_v3_v80_aug2026`.
- CRM case and MQC questions use `fact_agreement_context_poc_v3_v80_aug2026`.

Join a fact only to the dimensions needed to read its keys. Use the matching technical key columns such as `customer_key`, `agreement_key`, `sales_rep_key`, `reporting_week_key`, `month_key`, `service_key`, `tcr_key` and `category_key`. Never join one fact directly to another fact. If a question needs measures from more than one fact, calculate each fact separately and combine only the final labelled results.

Sum only additive TEU and count measures from the correct fact. Do not sum booleans, status text, scores, dates or cutoff fields. Do not average stored rates, percentages or existing averages. For row-level and ranking questions, use the stored rate at its own grain. If an aggregate rate cannot be calculated from approved numerator and denominator columns in the same fact, state that the requested aggregate rate is not supported.

Use dimensions only for names and filters. Preserve exact customer, agreement, sales representative, service, TCR, week and month values. The controlled unknown members preserve rows with missing source identifiers; do not discard or replace them. Never substitute a different customer when an exact customer has no result.

Generate read-only SQL only. Use explicit columns rather than `SELECT *`. Apply the question's filters exactly, use deterministic ordering, and return at most 20 rows unless the user asks for fewer. The attached data is a frozen August 2026 test sample, so do not present it as current production data.

Answer only what the attached facts and dimensions support. If the request needs another period, a source outside CSM/CSAL, a prediction, or a business rule not present in the data, explain the limitation without inventing an answer.
