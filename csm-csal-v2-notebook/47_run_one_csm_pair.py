# Databricks notebook cell
# Run the next unfinished CSM question against both benchmark agents.
# The checkpoint prevents a completed trial from being submitted twice.

csm_status()
run_next_csm_pairs(2)
csm_status()
