"""Build the paste-ready notebook from shared analysis and chart functions."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
PARTS = NOTEBOOKS / "customer-booking-patterns"

HEADER = '''# Databricks notebook source
# Paste this entire file into ONE Python cell. Run in the Windows VM.
# Existing CUSTOMER_RESULTS groups are reused. If absent, the same method rebuilds them.
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
import re
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from pyspark.sql import functions as F

TOP_CUSTOMERS = 25               # Distinct customers across all selected groups/services.
SELECT_SERVICES = None           # All available services; or ["PNW1", "PNW5"].
SELECT_CUSTOMERS = None          # Optional list of exact names; overrides top-25 selection.
AUDIT_TIMEZONE = "UTC"            # Confirmed by the user on 2026-09-23.
ROWS_PER_PAGE = 12
SHOW_FIRST_CUSTOMER = True
SHOW_TABLES = True
REBUILD_GROUPS = False           # True rebuilds; False preserves existing notebook groups.

# Used only when rebuilding the booking population and groups.
YEAR = 2026
SOURCE_SERVICES = None           # All services.
DAYS_BEFORE = 56
DAYS_AFTER = 14
MIN_BOOKINGS = 20
MIN_VOYAGES = 3
MIN_CUSTOMERS_PER_GROUP = 5
MAX_GROUPS = 8                    # Maximum to test; never forces three groups.
MIN_SILHOUETTE = 0.35
EXCLUDE_CUSTOMER_NAMES = ["Open Customers", "APN Unassigned"]

MAX_PROFILES = 100000
MAX_AUDIT_ROWS = 200000
MAX_DAILY_ROWS = 2000000
'''


def definitions(path, names=None):
    source = path.read_text()
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
             and (names is None or n.name in names)]
    if names is not None and {n.name for n in nodes} != set(names):
        raise ValueError(f"Missing helper in {path}")
    return "\n\n".join(ast.get_source_segment(source, n) for n in nodes)


def build():
    pieces = [HEADER, definitions(NOTEBOOKS / "csal-customer-bookings-and-extra-space.py", {
        "sql_text", "clean_customer", "booking_timing_sql", "extra_space_sql", "parse_audit_time",
        "classify_event_times", "summarize_extra_space"}),
        definitions(PARTS / "02_customer_groups_and_charts.py", {"assign_timing_groups"}),
        definitions(PARTS / "group_space_chart_helpers.py"),
        definitions(PARTS / "group_space_timeline_core.py"),
        'GROUP_SPACE_RESULTS = run_group_space_timeline()\nshow_group_customer = GROUP_SPACE_RESULTS["show_customer"]\n']
    target = NOTEBOOKS / "csal-group-customer-space-timeline.py"
    text = "\n\n\n".join(pieces)
    ast.parse(text)
    target.write_text(text)
    return target


if __name__ == "__main__":
    print(build())
