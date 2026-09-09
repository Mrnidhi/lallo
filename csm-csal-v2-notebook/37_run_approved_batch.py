# Notebook cell 12 (file 37) | Run the selected A/B pairs
# Start with MAX_TRIALS_THIS_RUN = 2: one question, once through each agent.
# The runner checks the saved experiment, request settings and scorer tests first.

if ENABLE_AGENT_RUNS:
    run_next_pairs(MAX_TRIALS_THIS_RUN)
else:
    print("Cell 12 is paused: ENABLE_AGENT_RUNS is False. This run submitted no questions.")
    print("When setup checks are complete, set ENABLE_AGENT_RUNS = True in a separate cell, then rerun cell 12.")
    print("After the first A/B pair, check both saved answers in cell 13 before increasing the batch size.")

# Rerun this cell to continue the same experiment. Saved trials are skipped.
# Never delete evidence or change the experiment label to make an uncertain request retry.
