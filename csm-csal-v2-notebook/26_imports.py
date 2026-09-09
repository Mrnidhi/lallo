# Notebook cell 1 (file 26) | Imports
# Use the personal 09-sales-ai-v2-benchmark notebook; leave the completed build cells unchanged.
# Run these cells one at a time, starting here.

from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
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
print("Imports ready. Next: cell 2, settings.")
