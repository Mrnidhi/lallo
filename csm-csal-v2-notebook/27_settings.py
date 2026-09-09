# Notebook cell 2 (file 27) | Set up the comparison
# Run once at the start of a session. The two execution switches start off.
# For later changes, update individual values rather than resetting this cell.

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
CODE_VERSION = "v2_remaining_cells_2"
EXPERIMENT_LABEL = "sales_ai_v2_first12_01"

# Leave these empty to select usable examples within each source.
# A matching name in two domains is not proof of a shared identity.
SALES_OVERRIDES = {"finance": None, "cases": None, "no_issues": None, "outlook": None}

# Record the checks completed against cells 3-6. Keep unfinished items False.
# These field names are retained so saved experiments stay compatible.
REVIEW = {
    "reviewer": "",
    "draft_sha256": "",  # Identifies the exact reference answers checked in cell 6.
    "business_logic_and_ground_truth": False,
    "source_local_fixtures": False,
    "ordering_and_precision": False,
    "current_agent_controls": False,
    "managed_model_limitation_accepted": True,
    "notes": "",
}

# Check the saved agent instructions, specialists and warehouse settings.
# The hashes below are reference values, not evidence of a new check.
CONTROL_EVIDENCE = {
    "checked_at_utc": "",
    "supervisor_instruction_sha256": "6fd1c60e2561d89c38e6b05415d084caaf052a700183d8218f6f271245369d2b",
    "csm_instruction_sha256": "6e0baefa73b1e847e46146e97732b014ded8e93710a2421f28ca496998349c7f",
    "same_shared_readers": False,
    "only_csm_reader_differs": False,
    "same_warehouse_and_settings": False,
}

# Cell 8 checks the endpoints. Set each request format from its own schema or UI example.
REQUEST_CONTRACT = {"A": None, "B": None}
REQUEST_SCHEMA_REVIEWED = {"A": False, "B": False}
ENABLE_EVIDENCE_SAVE = False
ENABLE_AGENT_RUNS = False
MAX_TRIALS_THIS_RUN = 2  # First run: one pair. Then raise, up to the remaining 72.
HTTP_TIMEOUT_SECONDS = 180
EVIDENCE_PATH = Path("/Workspace/Users/jayarsr@oocl.com/Sales AI EDA/v2-benchmark-evidence.json")

print("Plan: 12 questions × 2 supervisors × 3 repetitions = 72 trials.")
print("No enrichment, table rebuilds, new agents or production writes are included.")
print("Next: run cells 3, 4, 5 and 6 individually. Keep both execution switches off.")
