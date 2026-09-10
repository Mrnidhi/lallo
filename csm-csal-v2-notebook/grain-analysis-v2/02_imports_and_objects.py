# Cell 2 | Imports and personal POC objects

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from pyspark.sql import functions as F
from pyspark.sql import types as T


PERSONAL_SCHEMA = "usr.jayarsr"

WIDE_SOURCE = (
    PERSONAL_SCHEMA
    + ".src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23"
)
BOOKING_FACT = PERSONAL_SCHEMA + ".fact_booking_summary_poc_v2_v23"
COMMITMENT_FACT = PERSONAL_SCHEMA + ".fact_commitment_poc_v2_v23"
ALLOCATION_FACT = PERSONAL_SCHEMA + ".fact_allocation_poc_v2_v23"
BOOKING_VIEW = PERSONAL_SCHEMA + ".agent_booking_risk_current_poc_v2_v23"

BOOKING_GRAIN = ["customer", "agreement", "week_num", "service", "tcr"]

GRAIN_OBJECTS = [
    {
        "order": 1,
        "name": "Wide source",
        "table": WIDE_SOURCE,
        "grain_columns": BOOKING_GRAIN,
        "row_meaning": "Existing rows viewed at booking scope",
    },
    {
        "order": 2,
        "name": "Booking fact",
        "table": BOOKING_FACT,
        "grain_columns": ["booking_scope_key"],
        "row_meaning": "Customer + agreement + week + service + TCR",
    },
    {
        "order": 3,
        "name": "Commitment fact",
        "table": COMMITMENT_FACT,
        "grain_columns": ["commitment_scope_key"],
        "row_meaning": "Customer + agreement + week + service",
    },
    {
        "order": 4,
        "name": "Allocation fact",
        "table": ALLOCATION_FACT,
        "grain_columns": ["allocation_slice_key"],
        "row_meaning": "One detailed allocation slice",
    },
    {
        "order": 5,
        "name": "Booking view",
        "table": BOOKING_VIEW,
        "grain_columns": BOOKING_GRAIN,
        "row_meaning": "One agent-ready booking scope",
    },
]

PALETTE = {
    "wide": "#64748B",
    "booking": "#2563EB",
    "commitment": "#0F766E",
    "allocation": "#D97706",
    "view": "#7C3AED",
    "extra": "#F59E0B",
}

print("Ready to profile", len(GRAIN_OBJECTS), "personal objects.")
