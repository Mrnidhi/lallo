# Notebook cell 6 (file 31) | Review questions and expected answers before approval
# The base wording matches the numbered question bank. Real inputs stay here.

V2_BENCHMARK_READY = False
DRAFT_REVIEW_SHA256 = None
assert "PREPARATION_STAMPS" in globals(), "Run notebook cells 3-5 successfully first."
invalidate_preparation("questions")
assert "shared" in PREPARATION_STAMPS, "Notebook cell 5 has not completed successfully. Do not continue after an earlier cell failed."
require_preparation("shared", ground_truth_payload())
# These are the approved draft wording's fixed inputs, not freely editable filters.
assert FILTERS == {"week": "2026WK22", "service": "PVCS", "tcr": "HKG"}, "The question wording and configured filters differ. Review a new question version first."
assert MISSING_CUSTOMER == "CSM_POC_V2_NO_MATCH_20260901"
assert all(LOOKUP_FIXTURE[name] == FILTERS[key] for name, key in [("week_num", "week"), ("service", "service"), ("tcr", "tcr")])

QUESTIONS = {
    "C01": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations with the lowest confirmed utilization of their total reviewed commitment. Include confirmed TEU, total reviewed commitment and the utilization percentage. Only include combinations where the percentage can be calculated.",
    "C02": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as low booking. Include confirmed TEU, booked TEU and total reviewed commitment, with the lowest confirmed utilization first.",
    "C03": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as high cancellation. Include cancelled TEU, booked TEU and cancellation percentage, highest percentage first.",
    "C04": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as high rejection. Include rejected TEU, booked TEU and rejection percentage, highest percentage first.",
    "C05": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as above CSAL. Include booked TEU, confirmed TEU, total reviewed commitment and booking utilization, highest booking utilization first.",
    "C06": "Show the booking summary for customer {customer}, agreement {agreement}, week 2026WK22, service PVCS and TCR HKG. Include confirmed, cancelled, rejected, pended, terminated, no-show and total booked TEU. Return one summary, even if it appears against several allocation records.",
    "C07": "Show the booking summary for the exact customer name CSM_POC_V2_NO_MATCH_20260901, in week 2026WK22 and service PVCS. If there is no match, tell me. Do not substitute another customer.",
    "D01": "Using the latest snapshot in the finance source, show the 20 records with the largest outstanding balances for sales representative {sales}. Include customer, outstanding balance, oldest aging in days, recorded AR severity and snapshot date.",
    "D04": "Show the 10 cases with the highest recorded severity for sales representative {sales}. Include case ID, customer, state, severity, recommendation and the recorded data-as-of time.",
    "D06": "For sales representative {sales}, show up to 20 cases with no recorded issues. Include case ID, customer and state.",
    "D09": "For sales representative {sales}, show the most recently created Daily Outlook that is marked current. Include its ID, creation time and data-as-of time. Only retrieve the existing deliverable; do not create or send anything.",
    "R01": "Give me two separate lists: the 10 booking combinations marked as high cancellation with the highest cancellation percentages in week 2026WK22 and service PVCS, and the five finance records with the largest outstanding balances for sales representative {sales}, using the finance source's latest snapshot. Show the source and available data date for each list. Keep the lists separate; do not assume they describe the same customers.",
}
QUESTIONS["C06"] = QUESTIONS["C06"].format(**LOOKUP_FIXTURE)
for qid, domain in [("D01", "finance"), ("D04", "cases"), ("D06", "no_issues"), ("D09", "outlook"), ("R01", "finance")]:
    QUESTIONS[qid] = QUESTIONS[qid].format(sales=SALES_FIXTURES[domain])

# Deterministic ranking and display conventions must be identical in both arms.
# This appendix is explicit and versioned; it is not a silent question rewrite.
METHOD_VERSION = "v2_first12_order_precision_1"
booking_ties_note = "For ties, sort customer, agreement, week_num, service and TCR ascending, with missing values last. Keep TEU exact and NULL separate from zero."
finance_ties_note = "Keep balances to six decimals and missing values last. Break ties by customer, sales, sales_full, snapshot_date, overdue_invoices, max_aging_days, ar_severity, overdue_30_amount, overdue_60_amount and overdue_90_amount, ascending."
METHOD_NOTES = {
    "C01": "Rank on unrounded confirmed utilization; show the percentage to six decimals. " + booking_ties_note,
    "C02": "Rank on unrounded confirmed utilization, with missing percentages last. Keep all stored low-booking matches eligible. " + booking_ties_note,
    "C03": "Use the cancellation percentage rounded to two decimals for ranking and display. " + booking_ties_note,
    "C04": "Use the rejection percentage rounded to two decimals for ranking and display. " + booking_ties_note,
    "C05": "Use the booking-utilization percentage rounded to two decimals for ranking and display. " + booking_ties_note,
    "C06": "Keep the TEU values exact and NULL separate from zero.",
    "C07": "",  # No extra projection is required for a genuine no-match answer.
    "D01": finance_ties_note,
    "D04": "Keep numeric severity to six decimals, with missing values last. Break ties by case ID ascending. Preserve the recorded timestamp precision.",
    "D06": "Sort case ID ascending. A case must have no issue records at all, not just no active issues.",
    "D09": "Break creation-time ties by deliverable ID ascending, with missing creation times last. Preserve the recorded timestamp precision.",
    "R01": "For the booking list, use cancellation percentages rounded to two decimals for ranking and display. " + booking_ties_note + " For the finance list: " + finance_ties_note,
}
PROMPTS = {qid: question + ("\n\n" + METHOD_NOTES[qid] if METHOD_NOTES[qid] else "") for qid, question in QUESTIONS.items()}
TRACEABILITY = {
    "C01": "question_bank.md 1; FR-003; CSM column dictionary; confirmed utilization",
    "C02": "question_bank.md 2; FR-003; stored low-booking signal",
    "C03": "question_bank.md 3; FR-003; stored high-cancellation signal",
    "C04": "question_bank.md 4; FR-003; stored high-rejection signal",
    "C05": "question_bank.md 5; FR-003; stored above-CSAL signal",
    "C06": "question_bank.md 6; CSM grain/column lineage; repeated booking measures",
    "C07": "question_bank.md 7; exact-filter and no-match guardrail",
    "D01": "question_bank.md 15; finance specification; fincon_issues dictionary",
    "D04": "question_bank.md 18; FR-007/FR-008; case ledger dictionary",
    "D06": "question_bank.md 20; data-quality requirements; ledger/issue case_id relationship",
    "D09": "question_bank.md 23; FR-014; TEA data contract; task_name runtime binding",
    "R01": "question_bank.md 27; supervisor routing; separate C03 and D01 answers",
}
assert set(GT) == set(CONTRACTS) == set(QUESTIONS) == set(QUESTION_IDS)
DRAFT_REVIEW_SHA256 = fingerprint(review_payload())
preparation_stamp("questions", review_payload())


def show_review(qid):
    assert qid in QUESTION_IDS
    print(PROMPTS[qid])
    print("Requirement:", TRACEABILITY[qid])
    print("Expected grain:", "booking scope" if qid.startswith("C") else
          {"D01": "finance source record", "D04": "case_id", "D06": "case_id", "D09": "deliverable_id", "R01": "separate booking scopes and finance source records"}[qid])
    print("Expected source rows and SQL below remain inside this notebook:")
    for section, rows in GT[qid].items():
        print(section, stable_json(rows))
        print(GT_SQL[qid][section])


for qid in QUESTION_IDS:
    print(qid, {section: len(rows) for section, rows in GT[qid].items()}, "DRAFT")
print("Use show_review('C01') and the other IDs to inspect each answer and its SQL.")
print("Review the method appendix too. Share PROMPTS, not just the base wording, for an identical team test.")
print("Draft fingerprint to approve after review:", DRAFT_REVIEW_SHA256)
print("After review, complete REVIEW (including draft_sha256) and CONTROL_EVIDENCE in notebook cell 2, then run cell 7.")
