# Paste into a temporary Python cell at the bottom of the existing notebook.
# Run only this cell. Do not replace or rerun cell 12, and do not use Run all.
# This reads saved status only; it does not ask an agent or change the checkpoint.

if not callable(globals().get("load_checkpoint")):
    print("The saved-session helper is unavailable. Share this message before rerunning anything.")
else:
    saved_trials = load_checkpoint()["trials"]
    if not saved_trials:
        print("No trials are recorded in this checkpoint. Do not start another run yet.")
    for trial in saved_trials.values():
        print({
            name: trial.get(name)
            for name in ("question", "arm", "state", "error_type", "http_status")
        })
