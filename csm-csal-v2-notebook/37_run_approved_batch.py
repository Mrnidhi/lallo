# Notebook cell 12 (file 37) | Ask both agents
# Running this cell sends the next pair and saves both responses.
# Start with one pair. Read its results before running this cell again.

assert callable(globals().get("run_next_pairs")), "Run cells 7-11 first."
run_next_pairs(MAX_TRIALS_THIS_RUN)
print("Next: use cell 13 to compare the actual answers, then cell 14 for the report.")
