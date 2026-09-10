# CSM / CSAL simple before and after example

The values below are fictional. They are only used to explain the table design.

## The business question

> For week 2026WK22 and service PVCS, which booking scopes have high cancellation?

## Before: one wide table

The current wide structure keeps allocation detail, booking results and commitment values together.

| Customer | Agreement | Week | Service | TCR | Allocation category | Reviewed TEU | Booked TEU | Cancelled TEU | Total reviewed TEU | High cancellation |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| ABC Electronics | AG1001 | 2026WK22 | PVCS | HKG | Category 1 | 4 | 10 | 8 | 8 | Yes |
| ABC Electronics | AG1001 | 2026WK22 | PVCS | HKG | Category 2 | 2 | 10 | 8 | 8 | Yes |
| ABC Electronics | AG1001 | 2026WK22 | PVCS | HKG | Category 3 | 2 | 10 | 8 | 8 | Yes |

These are three valid allocation rows, but the booking and commitment numbers repeat on every row.

If an agent adds the columns without understanding the row meaning, it can report:

| Measure | Incorrect wide-table sum | Correct business value |
|---|---:|---:|
| Booked TEU | 30 | 10 |
| Cancelled TEU | 24 | 8 |
| Total reviewed TEU | 24 | 8 |

The wide table is not automatically wrong. It is simply asking one row to carry information from different business levels.

## Now: each table has one clear job

### Booking fact

One row represents one customer, agreement, week, service and TCR booking scope.

| Customer key | Agreement key | Week key | Service key | TCR key | Booked TEU | Cancelled TEU | High cancellation |
|---|---|---|---|---|---:|---:|---|
| C101 | A1001 | W202622 | S01 | T01 | 10 | 8 | Yes |

### Commitment fact

One row stores the reviewed commitment at customer, agreement, week and service level. TCR is not included because the commitment does not belong to individual TCR rows.

| Customer key | Agreement key | Week key | Service key | Total reviewed TEU |
|---|---|---|---|---:|
| C101 | A1001 | W202622 | S01 | 8 |

### Allocation fact

Allocation detail remains detailed because those rows are useful for allocation analysis.

| Customer key | Agreement key | Week key | Service key | TCR key | Category | Reviewed TEU |
|---|---|---|---|---|---|---:|
| C101 | A1001 | W202622 | S01 | T01 | Category 1 | 4 |
| C101 | A1001 | W202622 | S01 | T01 | Category 2 | 2 |
| C101 | A1001 | W202622 | S01 | T01 | Category 3 | 2 |

### Dimensions

Dimensions translate the short keys into readable business labels.

| Dimension | Key | Readable value |
|---|---|---|
| Customer | C101 | ABC Electronics |
| Agreement | A1001 | AG1001 |
| Week | W202622 | 2026WK22 |
| Service | S01 | PVCS |
| TCR | T01 | HKG |

Facts hold the numbers. Dimensions explain who, what and when those numbers belong to.

## What the agent sees

The booking view combines the required facts and dimensions before the agent asks a question.

| Customer | Agreement | Week | Service | TCR | Booked TEU | Cancelled TEU | Total reviewed TEU | Cancellation percentage | High cancellation |
|---|---|---|---|---|---:|---:|---:|---:|---|
| ABC Electronics | AG1001 | 2026WK22 | PVCS | HKG | 10 | 8 | 8 | 80% | Yes |

The agent receives one clear booking row instead of three allocation rows containing repeated booking values.

## Why this helps

| Wide-table path | Curated-view path |
|---|---|
| Agent searches across 78 columns | Agent searches across 29 relevant columns |
| Agent must recognize different row meanings | Booking row meaning is already declared |
| Agent may need to remove repeated values | Repeated booking rows are already handled |
| Similar metric names can be confusing | Percentage names are consistent |
| More room for incorrect aggregation | Agent mainly filters, sorts and returns the answer |

## The simple flow

```text
Dimensions give readable names
             +
Facts store numbers at the correct business level
             ↓
29-column booking view prepares one clear booking row
             ↓
Agent filters and answers the question
```

## What to say in the presentation

> Previously, booking and commitment values could repeat across detailed allocation rows. I separated those numbers into facts with clear row meanings, kept customer and service descriptions in dimensions, and gave the agent one prepared booking view. This makes the query easier and reduces the opportunity for double counting or choosing the wrong field.

The smaller view is easier for the agent to work with, but our test did not prove a faster end-to-end response. The measured response times were roughly the same. The improvement we observed was a small increase in answer accuracy.
