# Customer booking patterns around TCR cutoff

Use this to see when each customer usually books, which customers have similar habits, and how much their timing varies. It uses all services by default.

## Where to paste

In Databricks **inside the Windows VM**, create a notebook and set the cell language to **Python**.

Copy the entire contents of [customer_booking_patterns_all_in_one.py](customer_booking_patterns_all_in_one.py) into that cell and run it. No earlier notebook cells or temporary views are needed. Do not run both the combined file and the separate files.

The same code is also available as two files, pushed separately:

1. [01_booking_timing.py](01_booking_timing.py): booking population, route/cutoff matching and coverage.
2. [02_customer_groups_and_charts.py](02_customer_groups_and_charts.py): profiles, groups, history comparison and charts. Run it in the same notebook session after file 01.

The notebook reads three source tables and keeps its working data in the notebook session. It does not save or modify source tables. Python needs pandas, NumPy, Matplotlib and scikit-learn, in addition to Spark. The cell does not install packages or change compute settings.

## Settings at the top

| Setting | Default | What it changes |
|---|---|---|
| `YEAR` | `2026` | Year in which the original booking was created, using UTC. |
| `SERVICES` | `None` | All services. Use a list such as `["PNW5", "PNW1"]` to restrict the analysis. |
| `DAYS_BEFORE`, `DAYS_AFTER` | `56`, `14` | Shared comparison window, including day −56 and excluding exactly +14 days. |
| `MIN_BOOKINGS`, `MIN_VOYAGES` | `20`, `3` | Minimum history before a customer is assigned to an exploratory group. |
| `MIN_CUSTOMERS_PER_GROUP` | `5` | Smallest permitted group within a service. |
| `MAX_GROUPS` | `8` | Upper limit to test, not a required number of groups. |
| `MIN_SILHOUETTE` | `0.35` | Exploratory separation threshold. It is a configurable analysis choice, not a business rule. |
| `STABILITY_SHIFT_DAYS` | `7` | Flags a larger difference between earlier/later median booking times. |
| `CHART_SERVICE` | `None` | Automatically shows the service with the most customers eligible for grouping; all-service results remain in the tables. |
| `CHART_CUSTOMER` | `None` | Optional customer name for the second chart and customer daily table. |
| `MAX_CUSTOMERS_ON_CHART` | `25` | Limits the displayed comparison to the largest customer histories; the lookup table contains everyone. |
| `EXCLUDE_CUSTOMER_NAMES` | Two known pooled names | `Open Customers` and `APN Unassigned` remain in coverage but are not treated as individual customers. Edit if needed. |

Change data or grouping settings and rerun the combined cell. To switch the charts after the run, a small additional Python cell is enough:

```python
show_customer_service("PNW1")
```

For one customer:

```python
show_customer_service("PNW1", "Customer name from the lookup table")
```

## What the results mean

**Customer lookup:** one row per customer name and service, with available year bookings, included booking count and coverage percentage, voyage count, typical booking day, middle 50% range, after-cutoff share and the earlier/later history check. Low coverage means the pattern describes only a small part of that customer's available bookings. Customers with no usable profile are listed separately. A customer may have different habits on different services. Names are normalized for spacing and capitalization; aliases and related companies are not merged. Records with unresolved year or conflicting current identity/route are counted in service coverage and kept out of customer-specific coverage denominators.

**Chart 1 — When customers usually book:** one daily curve for each group in the selected service. Each customer's daily booking shares are averaged, so a large customer does not dominate the group. The daily table also supplies the exact number of bookings on every day for each group. A customer with limited history remains in the lookup but is excluded from these group curves.

**Chart 2 — Customer booking windows:** the dot is the customer's median booking day; the line contains the middle 50% of their bookings. A long line means timing varies. Grey means there is not enough history for grouping. The accompanying customer daily table provides the actual daily counts.

Negative days are before TCR cutoff. Day zero begins at the cutoff timestamp and spans the next 24 hours. The table separates bookings exactly at the cutoff from those strictly after it. Daily bins use elapsed time, not local calendar dates.

For example, at day −15 a usual window of −24 to −19 has passed, while −8 to −4 is still ahead. This describes a customer's history. It does not prove that an absent customer will not book or authorize reallocating their space.

## Population and checks

- `csal_shipment.rec_cre_dt_utc` is treated as original booking time based on the user's confirmation on September 23, 2026. Customer name comes from `csal_booking_detail.ccp_cus_nme`.
- The base population is bookings created in the selected year, through the run time, that appear in available booking detail. Shipment records without booking detail are outside this population. Rows with unresolved creation time are listed separately because their year cannot be assigned.
- Every included cutoff must allow the whole comparison window inside the selected year through the run time. With the defaults, the first eligible cutoff is February 26, 2026. The most recent eligible cutoff is 14 days before the run time. Bookings outside −56 to +14 days are counted in coverage and excluded from profiles; this is not a full-lifetime booking distribution.
- Source history completeness is not established merely because a window has elapsed. Coverage is reported by service so a low match rate cannot be mistaken for a complete customer history.
- One shipment contributes one booking. Tied conflicting customer/route records and inconsistent booking times are excluded. Duplicate copies of the same projected source record do not increase counts.
- Current corporate and first-loading voyages/ports must identify the same leg. Connecting routes are shown in coverage instead of assigning them a possibly wrong cutoff. Multiple calls at the same port require a unique exact loading-departure match. Omitted, tentative and otherwise unavailable calls remain excluded.
- The vessel/port assignment and cutoff are the latest available values. This does not reconstruct the schedule or ownership at booking time. All current shipment statuses, including cancelled and rejected, are retained for original booking activity; this is not net active demand.
- Within each service, K-means uses the customer's 25th, 50th and 75th percentile booking days. Booking volume is not an input feature. The code tests supported group counts, checks minimum group size and uses silhouette separation. If no useful split is found, it keeps one shared pattern and says so. It does not force five or ten groups.
- The history check splits voyages into earlier and later cutoff periods; a voyage stays in one period. Both periods need at least five bookings across two voyages for a customer. A similar median is a limited consistency check, not full validation of a predictive model.

K-means selection follows the approach described in the [scikit-learn silhouette example](https://scikit-learn.org/stable/auto_examples/cluster/plot_kmeans_silhouette_analysis.html). UTC comparisons use elapsed microseconds; see [Databricks `unix_micros`](https://docs.databricks.com/aws/en/sql/language-manual/functions/unix_micros).

## Validation status

The code is checked locally with synthetic data, including SQL joins, timing boundaries, customer weighting and chart rendering. It still needs a run against the live Databricks tables. The notebook returns the complete available customer/group tables and two figures; it does not claim confirmed swaps or a validated recommendation date.
