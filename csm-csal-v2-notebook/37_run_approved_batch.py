# Notebook cell 12 (file 37) | Run the approved batch, starting with one A/B pair
# Leave disabled until the review, checkpoint, request-schema and self-test gates pass.

if ENABLE_AGENT_RUNS:
    run_next_pairs(MAX_TRIALS_THIS_RUN)
else:
    print("Agent runs are disabled. No question was submitted.")
    print("After the first pair, inspect both recorded responses before increasing the batch size.")

# Rerun this cell to continue the same experiment. Saved trials are skipped.
# Never delete evidence or change the experiment label to make an uncertain request retry.
