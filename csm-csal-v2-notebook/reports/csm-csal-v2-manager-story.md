# CSM / CSAL V2 manager story

## One-minute version

I started with a simple question: can we make the CSM agent more reliable without changing production?

I kept a frozen personal copy of the current 78-column table as the baseline. Beside it, I built a smaller booking view over facts and dimensions, with one clear booking scope and only the fields the agent needs.

I then asked both personal agent setups the same seven technically cross-checked questions three times each. That gave us 42 completed responses. Across the 18 C01-C06 table-answer runs per setup, the curated path scored 72.2% and the wide path scored 66.7%. The curated path was one answer better overall. Both paths were stable for three of four comparable question groups, and there was no clear response-time winner at about 40 seconds.

So the result is positive, but not strong enough to justify replacing production. My recommendation is to keep production unchanged, continue the curated booking view as a pilot, fix the remaining output-format and ranking issues, capture the real SQL trace, and repeat the same controlled test before expanding to other business areas.

## Short answer if asked what improved

The smaller view gave a modest accuracy improvement. It did not show a clear speed improvement, and it did not remove every answer-format problem. Because Databricks manages the underlying model, this result compares the complete agent setups rather than proving that the table design alone caused the difference.

## Short answer if asked what is next

We should correct C01, C03 and C06 agent instructions, capture the executed SQL and rerun the same 42 trials. The broader 41-question bank, threshold calibration, historical enrichment and swap scoring should remain separate follow-up work.

- [Full evidence](csm-csal-v2-controlled-benchmark-results-2026-09-10.md)
- [One-page comparison](csm-csal-v2-manager-benchmark-report.md)
