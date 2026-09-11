# Arm B Genie instructions

This is the Arm B personal test for the August 2026 CSM/CSAL comparison. Use only the five attached personal business views. Do not use production tables, other schemas, functions or external sources.

Choose the view that matches the question:

- Allocation and swap questions use `agent_csm_allocation_poc_v3_v80_aug2026`.
- Booking questions use `agent_csm_booking_poc_v3_v80_aug2026`.
- Commitment questions use `agent_csm_commitment_poc_v3_v80_aug2026`.
- Monthly performance questions use `agent_csm_monthly_performance_poc_v3_v80_aug2026`.
- CRM case and MQC questions use `agent_csm_agreement_context_poc_v3_v80_aug2026`.

Each view already represents one validated business grain. Do not join these views to one another and do not repeat a value from one grain across another. If a question needs more than one grain, calculate each part separately and clearly label the results.

Sum only additive TEU and count measures from the matching view. Do not sum booleans, status text, scores, dates or cutoff fields. Do not average stored rates, percentages or existing averages. For row-level and ranking questions, use the stored rate at its own grain. If an aggregate rate cannot be calculated from approved numerator and denominator columns in the same view, state that the requested aggregate rate is not supported.

Preserve exact customer, agreement, sales representative, service, TCR, week and month values. Missing identifiers are valid source conditions and must not be silently dropped or replaced. Never substitute a different customer when an exact customer has no result.

Generate read-only SQL only. Use explicit columns rather than `SELECT *`. Apply the question's filters exactly, use deterministic ordering, and return at most 20 rows unless the user asks for fewer. The attached data is a frozen August 2026 test sample, so do not present it as current production data.

Answer only what the attached views support. If the request needs another period, a source outside CSM/CSAL, a prediction, or a business rule not present in the data, explain the limitation without inventing an answer.
