# V3 personal model publishing cells

Add these four Python cells after Cell 20 of `01_csm_csal_grain_and_key_validation`.

Run the notebook from Cell 1. Continue only when Cell 20 prints:

`READY_FOR_PERSONAL_ARM_C_POC_BUILD`

Then run:

1. `21_persist_validated_model.py`
2. `22_validate_persisted_model.py`
3. `23_create_business_views.py`
4. `24_publish_summary.py`

The last cell must print:

`READY_FOR_V3_PERSONAL_AGENT_CONFIGURATION`

The cells write only to `usr.jayarsr`. They create or replace 8 dimensions, 5 facts and 5 read-only business views using the frozen August 2026 sample from source version 80. Rerunning the cells uses the same object names and is idempotent.

Do not configure either personal Genie until all Cell 22 and Cell 23 checks show `PASS`.
