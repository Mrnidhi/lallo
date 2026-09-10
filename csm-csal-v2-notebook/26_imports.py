# Cell 1 | Imports
# Use the personal 09-sales-ai-v2-benchmark notebook; leave the completed build cells unchanged.
# Run these cells one at a time, starting here.

from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from importlib.metadata import version as package_version
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import inspect
import json
import math
import os
import re
import statistics
import tempfile
import time

from databricks.sdk import WorkspaceClient
from pyspark.sql import functions as F, types as T

V2_BENCHMARK_READY = False
print("Installed packages:", {name: package_version(name) for name in ("databricks-connect", "openai", "databricks-sdk", "httpx")})
print("Imports ready. Next: cell 2, settings.")
