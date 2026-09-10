# CSM / CSAL V2 presentation guide

## One-minute version

I started with one question: can a simpler data structure help the CSM agent answer more reliably without changing production?

I kept production untouched and created a frozen personal baseline from the existing 78-column Gold-shaped table. I then separated the data into three clear business areas: booking, commitment and allocation. Each area has its own row meaning, supported by shared dimensions such as customer, agreement, week, service and TCR.

For the agent test, I exposed a smaller 29-column booking view and compared it with the frozen wide-table path. Both personal agent setups received the same seven questions three times, giving 42 completed responses.

Across the C01 to C06 table-answer runs, the wide path scored 66.7 percent and the curated path scored 72.2 percent. That is one additional correct response. Response time remained close to 40 seconds for both, so there was no clear speed winner.

My recommendation is to keep production unchanged, improve the remaining agent response rules, capture complete SQL traces and repeat the same controlled test before expanding to other business areas.

## Step-by-step presentation

### Step 1: Explain why I started

> The current CSM Gold-shaped table exposes 78 columns. It contains measures that are useful at different business levels, which can make it harder for an agent to choose the correct column and aggregation. I wanted to test whether a smaller, clearly defined data path could improve the answers.

Main point: this was a reliability test, not a production replacement.

### Step 2: Explain the safety boundary

> I did all the work in my personal Databricks workspace. I did not modify the production Gold table, production logic, jobs, functions or production agents.

I used a frozen personal copy so both test paths could be compared against a stable source.

### Step 3: Explain grain in simple words

> Grain means what one row represents. Instead of treating all measures as if they belong at the same level, I separated them by their actual business meaning.

| Area | What one row represents |
|---|---|
| Booking fact | Customer, agreement, reporting week, service and TCR |
| Commitment fact | Customer, agreement, reporting week and service |
| Allocation fact | Month, week, customer, sales representative, agreement, TCR, service and category |

The booking path removed 3,978 repeated physical rows at its five-column grain. This is a 1.64 percent reduction from 242,370 wide rows to 238,392 booking scopes.

Do not say that all grains were reduced. The commitment fact is smaller because it represents a different four-part business scope. The allocation fact intentionally keeps the detailed allocation rows.

### Step 4: Explain what I built

> I created a personal proof-of-concept model with three facts and seven shared dimensions. The dimensions provide readable context, while each fact stores measures at one declared business grain.

The dimensions cover:

- Customer
- Agreement
- Reporting week
- Service
- TCR
- Sales representative
- Category

I then created a 29-column booking view for the agent. It combines the booking and commitment information with the five dimensions needed for booking questions.

#### What the fact tables contain

A fact table mainly holds the numbers we want to measure. The examples below show the useful business columns, not every technical audit field.

| Fact table | Sample columns | Simple meaning |
|---|---|---|
| `fact_booking_summary_poc_v2_v23` | customer, agreement, week, service, TCR, confirmed TEU, cancelled TEU, rejected TEU, booked TEU and the current risk flags | What happened to booking demand at one booking scope |
| `fact_commitment_poc_v2_v23` | customer, agreement, week, service and total reviewed TEU | The reviewed commitment stored once at its correct level |
| `fact_allocation_poc_v2_v23` | month, week, customer, sales representative, agreement, TCR, service, category, original TEU, reviewed TEU and final TEU | The detailed allocation position used for allocation analysis |

#### What the dimension tables contain

A dimension table gives those numbers readable context. The actual tables also contain interim identity and audit fields, but they are left out here because these are business examples, not full schemas.

| Dimension table | Sample columns | What it helps us understand |
|---|---|---|
| `dim_customer_poc_v2_v23` | customer | Who the result belongs to |
| `dim_agreement_poc_v2_v23` | agreement | Which commercial agreement applies |
| `dim_week_poc_v2_v23` | week_num | When the result applies |
| `dim_service_poc_v2_v23` | service | Which shipping service applies |
| `dim_tcr_poc_v2_v23` | tcr | Which trade or commercial route applies |
| `dim_sales_rep_poc_v2_v23` | sales_rep | Who owns the allocation relationship |
| `dim_category_poc_v2_v23` | category | Which allocation category applies |

The prepared booking view brings together fields such as customer, agreement, week, service, TCR, confirmed TEU, booked TEU, cancelled TEU, total reviewed TEU, fulfillment percentage, cancellation percentage and the current stored risk flags. The agent normally reads this view instead of working through the facts and dimensions itself.

> A simple way to explain it is: facts hold the numbers, dimensions explain the numbers, and the booking view gives the agent one prepared place to read both.

### Step 5: Show the before and after paths

| Before | After |
|---|---|
| Frozen personal copy of the 78-column Gold-shaped table | Personal 29-column curated booking view |
| Wide baseline agent path | Booking-scope agent path |
| More fields and more possible interpretations | Smaller interface with a declared booking grain |

> The purpose was not simply to remove columns. The purpose was to give the agent a clearer data contract.

### Step 6: Show how a question becomes simpler

Example business question:

> For week 2026WK22 and service PVCS, show the 20 booking scopes currently marked as high cancellation, starting with the highest cancellation percentage.

The following SQL is an illustrative comparison based on the verified grain rules. It is not a claim that the production agent executed these exact statements, because complete executed SQL traces were not available.

Before, the wide path has to remove repeated physical rows and translate the wide-table rate name into the agreed output name:

```sql
WITH booking_scope AS (
  SELECT DISTINCT
    customer,
    agreement,
    week_num,
    service,
    tcr,
    booked_teu,
    cancelled_teu,
    cancellation_rate,
    is_high_cancellation
  FROM usr.jayarsr.src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23
  WHERE week_num = '2026WK22'
    AND service = 'PVCS'
),
prepared AS (
  SELECT
    *,
    cancellation_rate AS cancellation_pct
  FROM booking_scope
)
SELECT
  customer,
  agreement,
  tcr,
  booked_teu,
  cancelled_teu,
  cancellation_pct
FROM prepared
WHERE is_high_cancellation = true
ORDER BY
  cancellation_pct DESC NULLS LAST,
  customer,
  agreement,
  week_num,
  service,
  tcr
LIMIT 20;
```

Now, the curated path reads the prepared booking view directly:

```sql
SELECT
  customer,
  agreement,
  tcr,
  booked_teu,
  cancelled_teu,
  cancellation_pct
FROM usr.jayarsr.agent_booking_risk_current_poc_v2_v23
WHERE week_num = '2026WK22'
  AND service = 'PVCS'
  AND is_high_cancellation = true
ORDER BY
  cancellation_pct DESC NULLS LAST,
  customer,
  agreement,
  week_num,
  service,
  tcr
LIMIT 20;
```

> The second query is easier because the data layer has already handled the booking grain and percentage name. The agent only applies the requested week, service and stored flag, then sorts the answer. That gives it fewer opportunities to select the wrong field or count the same booking value more than once.

### Step 7: Explain how I tested it

> I used seven technically cross-checked booking questions. I asked every question three times through each personal agent path.

The test size was:

`7 questions x 3 repetitions x 2 agent paths = 42 completed responses`

Both paths used the same question wording and result rules. The calls were recorded without silently retrying failed or uncertain answers.

### Step 8: Present the result honestly

| Measure | Wide path | Curated path |
|---|---:|---:|
| C01 to C06 table-answer accuracy | 66.7% | 72.2% |
| Correct table-answer runs | 12 of 18 | 13 of 18 |
| Median client response time | 40.98 seconds | 40.09 seconds |

> The curated path returned one additional correct answer, which is a useful early signal. Response time was effectively tied, so I am not claiming a speed improvement.

Both paths still had issues with one unstable ranking question and with required fields not always appearing in the expected response format.

### Step 9: Explain what the test did not prove

This proof of concept did not prove that:

- The production Gold table should be replaced.
- Facts and dimensions alone caused the accuracy difference.
- The curated view is faster.
- The existing risk thresholds are correct.
- Historical trends, swap recommendations or other business domains are supported.
- SQL correctness or SQL execution time improved, because complete executed SQL traces were not available.

The test covered booking-scope questions only. It did not validate the complete 41-question bank.

### Step 10: Give the recommendation

> Keep production unchanged and continue the 29-column booking view as a controlled personal pilot. First, improve the response rules for the questions that were unstable or missing fields. Then capture the selected source and complete executed SQL for every run, repeat the same 42-response test and only then expand to more business areas.

## Next steps

1. Keep the production table and production agents unchanged.
2. Tighten the agent response contract for C01, C03 and C06.
3. Capture complete source and SQL evidence for every response.
4. Repeat the same 42-response test without changing the ground truth.
5. Expand gradually to the remaining verified question-bank categories.
6. Treat threshold calibration, historical enrichment and swap scoring as separate follow-up work.

## Five facts to remember

1. The baseline had 78 columns.
2. The curated booking view has 29 columns.
3. Booking, commitment and allocation were separated by row meaning.
4. The test completed 42 agent responses.
5. Accuracy moved from 66.7 percent to 72.2 percent, while latency had no clear winner.

## If I am asked difficult questions

### Why not replace production now?

> The result is positive but small. It covers only one business area and does not include complete SQL trace evidence. Another controlled round is needed before any production decision.

### Did the new design make the agent faster?

> No clear speed improvement was proven. Both paths were close to 40 seconds, and the different latency comparisons did not point consistently in one direction.

### Is the fact-and-dimension model working?

> Its structural checks passed and the booking view was usable by the agent. The benchmark showed a small accuracy improvement, but the complete architecture still needs broader testing.

### What was the main learning?

> A clearer data interface can help, but data modelling alone is not enough. Reliable agent answers also need strict output rules, stable ranking behaviour and complete trace evidence.

## Closing sentence

> I have shown that the curated booking path is feasible and slightly more accurate in this controlled personal test. The responsible next step is to strengthen the agent contract and evidence, rerun the same test and expand only when the result is repeatable.
