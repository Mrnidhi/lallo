# Cell 2 | Set up the comparison
# Run at the start of a session. Cell 7 saves the setup; only cell 12 asks agents.

V2_BENCHMARK_READY = False
PERSONAL_OWNER = "jayarsr@oocl.com"
PERSONAL_SCHEMA = "usr.jayarsr"
BASELINE = PERSONAL_SCHEMA + ".src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23"
BASELINE_VERSION = 0  # Personal copy of original Gold v32. The suffix is a build label.
BOOKING_VIEW = PERSONAL_SCHEMA + ".agent_booking_risk_current_poc_v2_v23"
ENDPOINTS = {"A": "mas-3beadca0-endpoint", "B": "mas-6b7af80b-endpoint"}
WAREHOUSE_ID = "e01805775d74d241"
SOURCES = {
    "finance": "dev.sales_ai_assistant_gold.fincon_issues",
    "cases": "dev.sales_ai_assistant_gold.sales_ai_case_ledger",
    "issues": "dev.sales_ai_assistant_gold.sales_ai_case_issues",
    "roster": "dev.sales_ai_assistant_gold.sales_ai_roster",
    "outlook": "dev.sales_ai_assistant_gold.tea_deliverables",
    "detail": "dev.crmi_gold.csal_teu_performance",
}
CSM_DEPENDENCIES = [BASELINE] + [
    PERSONAL_SCHEMA + "." + name + "_poc_v2_v23"
    for name in ["fact_booking_summary", "fact_commitment", "dim_customer",
                 "dim_agreement", "dim_week", "dim_service", "dim_tcr"]
]
SCOPE = "customer agreement week_num service tcr".split()
BOOKING_MEASURES = "confirmed_teu cancelled_teu rejected_teu pended_teu terminated_teu no_show_teu booked_teu".split()
MEASURES = BOOKING_MEASURES + ["total_reviewed_teu"]
FLAGS = "is_low_booking is_high_cancellation is_high_rejection is_above_csal".split()
FILTERS = {"week": "2026WK22", "service": "PVCS", "tcr": "HKG"}
MISSING_CUSTOMER = "CSM_POC_V2_NO_MATCH_20260901"
DAILY_OUTLOOK_TASK = "DAILY_OUTLOOK"  # Verify the task_name value, not deliverable_type.
QUESTION_IDS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "D01", "D04", "D06", "D09", "R01"]
REPETITIONS = 3
WORDING_VERSION = "v2_question_wording_2"
CODE_VERSION = "v2_routing_contract_1"
EXPERIMENT_LABEL = "sales_ai_v2_first12_routing_01"
ROUTING_CONTRACT = {
    "version": "csm_summary_routing_1",
    "instruction_sha256": "34e216536917b68ec6fa530630e375e909d51ce53ad066529815a9b5ef1a7398",
    "csm_readers": {"A": "CSM Wide Baseline V2", "B": "CSM Booking Scope V2"},
    "verification": "Saved supervisor text was manually read back after refresh before this experiment. The notebook does not fetch supervisor settings.",
}

# Leave these empty to select usable examples within each source.
# A matching name in two domains is not proof of a shared identity.
SALES_OVERRIDES = {"finance": None, "cases": None, "no_issues": None, "outlook": None}

# Both saved endpoint examples use the Responses input format.
REQUEST_CONTRACT = {"A": "input", "B": "input"}
MAX_TRIALS_THIS_RUN = 2  # One question through A and B per run of cell 12.
HTTP_TIMEOUT_SECONDS = 180
# This is a separate routing-contract comparison, not a retry of an earlier request.
# Keep all previous evidence files unchanged; do not copy their trials here.
EVIDENCE_PATH = Path("/Workspace/Users/jayarsr@oocl.com/Sales AI EDA/v2-benchmark-routing1-evidence.json")

print("Plan: 12 questions × 2 supervisors × 3 repetitions = 72 trials.")
print("Routing contract:", ROUTING_CONTRACT["version"])
print("No enrichment, table rebuilds, new agents or production writes are included.")
print("Next: run cells 3-6 individually to prepare the reference answers.")
print("All 41 questions remain the full target; these 12 are the ready-to-test subset.")
