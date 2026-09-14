# Review of the reported production fix

Revised after reviewing the assumptions behind the earlier grain comparison.

The supplied team-message screenshot reports a fix for a specific duplicate-record issue affecting swap demand in Daily Outlook, with the corrected output expected after a job rerun. The screenshots do not establish its full implementation scope or verify the post-rerun result.

The SQL screenshot shows different totals from direct summation and the proposed grouped calculation. That is an observation requiring explanation. It does not by itself prove that the production fix failed, that every grain is wrong, or that the smaller grouped total is the correct business answer.

The earlier statement that all ten metrics "remain unsafe" was too definite without checking current within-group consistency, missing keys, identity semantics, source lineage and the consuming query. Use the corrected [grain-review notebook](../grain-review/README.md) to make those assumptions visible.

What can currently be stated:

- A targeted swap-demand fix was reported; post-fix validation is still needed.
- Direct and proposed-group totals differed in the supplied SQL output.
- The current screenshot did not visibly pin a Delta version, so it cannot be paired automatically with historical v86 agent responses.
- Monthly, booking, commitment, allocation, swap, MQC, percentage and context fields require checks appropriate to their business meaning.
- Passing column preservation or sample-constancy checks does not establish approved business grain, entity identity or additivity.
- No finding from this screenshot alone establishes that all other metrics are correct or incorrect.

Next, record the post-rerun source version, inspect the deployed fix and its intended scope, run the neutral checks against that version, and compare the relevant production-agent answer using aligned data and its actual SQL/tool trace where available. Retain correct and unresolved outcomes alongside discrepancies.
