# Databricks notebook source
# Run after 01, or run the combined file instead of both separate files.
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from pyspark.sql import functions as F


def assign_timing_groups(profiles, min_bookings=20, min_voyages=3,
                         min_group_size=5, max_groups=8, min_silhouette=0.35):
    """One equally weighted customer per service; volume is not a clustering feature."""
    result = profiles.copy()
    result["timing_group"] = "Limited history"
    result["group_note"] = "More bookings or voyages needed"
    result["group_order"] = 99
    if min_bookings < 1 or min_voyages < 1 or min_group_size < 2 or not 2 <= max_groups <= 20:
        raise ValueError("Check the grouping minimums and MAX_GROUPS (2–20).")
    if not 0 <= min_silhouette <= 1:
        raise ValueError("MIN_SILHOUETTE must be between 0 and 1.")
    diagnostics = []
    for service, service_rows in result.groupby("service", sort=True):
        eligible = service_rows[(service_rows.bookings >= min_bookings) &
                                (service_rows.voyages >= min_voyages)]
        if eligible.empty:
            diagnostics.append({"service": service, "customers_for_grouping": 0,
                                "groups": 0, "silhouette": None,
                                "decision": "Not enough customer history"})
            continue
        x = eligible[["p25_day", "median_day", "p75_day"]].to_numpy(dtype=float)
        candidates = []
        upper = min(max_groups, len(x) // min_group_size, len(np.unique(x, axis=0)))
        for k in range(2, upper + 1):
            labels = KMeans(n_clusters=k, n_init=10, max_iter=200,
                            random_state=42).fit_predict(x)
            _, sizes = np.unique(labels, return_counts=True)
            if len(sizes) != k or sizes.min() < min_group_size:
                continue
            # Keep each group represented if the silhouette calculation is sampled.
            if len(x) > 2000:
                rng = np.random.default_rng(42)
                seeds = np.concatenate([rng.choice(np.flatnonzero(labels == g), 2, replace=False)
                                        for g in range(k)])
                rest = np.setdiff1d(np.arange(len(x)), seeds)
                sample = np.concatenate([seeds, rng.choice(rest, 2000 - len(seeds), replace=False)])
            else:
                sample = np.arange(len(x))
            score = float(silhouette_score(x[sample], labels[sample]))
            candidates.append((k, score, labels))
        supported = [c for c in candidates if c[1] >= min_silhouette]
        if supported:
            best = max(c[1] for c in supported)
            k, score, labels = min((c for c in supported if c[1] >= best - 0.02),
                                   key=lambda c: c[0])
            note = "Exploratory timing group"
        else:
            k, score, labels = 1, None, np.zeros(len(x), dtype=int)
            note = "No clear separation into smaller groups"
        order = sorted(np.unique(labels), key=lambda g: float(np.median(x[labels == g, 1])))
        for position, raw_group in enumerate(order, 1):
            indexes = eligible.index[labels == raw_group]
            result.loc[indexes, "timing_group"] = f"G{position}"
            result.loc[indexes, "group_note"] = note
            result.loc[indexes, "group_order"] = position
        diagnostics.append({"service": service, "customers_for_grouping": len(x),
                            "groups": k, "silhouette": score,
                            "decision": note})
    return result, pd.DataFrame(diagnostics)


def describe_day(value):
    value = float(value)
    if abs(value) < 0.05:
        return "at cutoff"
    return f"{abs(value):.1f} days {'before' if value < 0 else 'after'}"


def customer_weighted_curves(daily, membership, days):
    """Zero-filled daily shares, averaged across customers in each timing group."""
    joined = daily.merge(membership[["customer_key", "service", "timing_group", "bookings"]],
                         on=["customer_key", "service"], how="inner", validate="many_to_one")
    joined["customer_daily_pct"] = 100.0 * joined["daily_bookings"] / joined["bookings"]
    observed = joined.groupby(["service", "customer_key"]).daily_bookings.sum()
    expected = membership.set_index(["service", "customer_key"]).bookings
    if not observed.reindex(expected.index, fill_value=0).eq(expected).all():
        raise ValueError("Daily counts do not reconcile to customer profiles. Rerun the combined cell.")
    sizes = membership.groupby("timing_group").size()
    output = []
    for group, size in sizes.items():
        rows = joined[joined.timing_group == group]
        counts = rows.groupby("day_from_cutoff").daily_bookings.sum().reindex(days, fill_value=0)
        shares = (rows.groupby("day_from_cutoff").customer_daily_pct.sum()
                  .reindex(days, fill_value=0) / size)
        for day in days:
            output.append({"timing_group": group, "day_from_cutoff": int(day),
                           "bookings": int(counts.loc[day]),
                           "mean_customer_booking_pct": float(shares.loc[day])})
    return pd.DataFrame(output)


def plot_customer_patterns(curves, profiles, service, days_before, days_after,
                          customer=None, max_customers=25):
    navy, red, grey = "#203D60", "#D20A2E", "#707B87"
    group_rows = profiles[profiles.timing_group != "Limited history"]
    ordered_groups = (group_rows[["timing_group", "group_order"]].drop_duplicates()
                      .sort_values("group_order").timing_group.tolist())
    if ordered_groups:
        fig, axes = plt.subplots(len(ordered_groups), 1,
                                 figsize=(12, max(3, 2.3 * len(ordered_groups))),
                                 sharex=True, squeeze=False)
        for ax, group in zip(axes.flat, ordered_groups):
            line = curves[curves.timing_group == group]
            members = group_rows[group_rows.timing_group == group]
            ax.plot(line.day_from_cutoff, line.mean_customer_booking_pct, color=navy, lw=1.8)
            ax.axvline(0, color=red, lw=1.2)
            label = "All eligible customers" if members.group_note.iloc[0].startswith("No clear") else group
            ax.set_title(f"{label}  ·  Usually {describe_day(members.median_day.median())}"
                         f"  ·  {len(members):,} customers / {int(members.bookings.sum()):,} bookings",
                         loc="left", fontsize=10, color=navy)
            ax.set_ylabel("Bookings (%)", fontsize=9)
            ax.set_ylim(bottom=0)
            ax.grid(axis="y", color="#E5E9EF", lw=0.6)
            ax.spines[["top", "right"]].set_visible(False)
        axes[-1, 0].set_xlabel("Days from TCR cutoff  |  0 = cutoff; negative = before")
        axes[-1, 0].set_xlim(-days_before, days_after)
        axes[-1, 0].xaxis.set_major_locator(MaxNLocator(integer=True, nbins=12))
        fig.suptitle(f"When customers usually book · {service}", x=0.09, ha="left",
                     fontsize=15, color=navy, fontweight="bold")
        fig.text(0.09, 0.012, "Each customer has equal weight. Daily bins begin at the cutoff time."
                 " Exact booking counts are in the daily table.", fontsize=9, color=grey)
        fig.tight_layout(rect=(0, 0.04, 1, 0.97))
        plt.show()
        plt.close(fig)
    shown = profiles.copy()
    if customer:
        key = " ".join(str(customer).split()).upper()
        shown = shown[shown.customer_key == key]
    else:
        shown = shown.sort_values(["bookings", "customer_key"], ascending=[False, True]).head(max_customers)
    shown = shown.sort_values(["median_day", "customer_key"])
    if shown.empty:
        print("No customer matches CHART_CUSTOMER in this service.")
        return
    fig, ax = plt.subplots(figsize=(12, max(4, 0.38 * len(shown) + 1.7)))
    for y, (_, row) in enumerate(shown.iterrows()):
        colour = grey if row.timing_group == "Limited history" else navy
        ax.plot([row.p25_day, row.p75_day], [y, y], color=colour, lw=4, solid_capstyle="round")
        ax.plot(row.median_day, y, "o", color=red, markersize=5)
    ax.axvline(0, color=red, lw=1, linestyle="--")
    labels = [f"{r.customer[:60]} · {r.timing_group} · n={int(r.bookings):,}"
              for r in shown.itertuples()]
    ax.set_yticks(np.arange(len(shown)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(-days_before, days_after)
    ax.set_xlabel("Days from TCR cutoff")
    ax.set_title(f"Customer booking windows · {service}", loc="left", color=navy,
                 fontsize=15, fontweight="bold", pad=20)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#E5E9EF", lw=0.6)
    fig.text(0.02, 0.012, "Dot = median. Line = middle 50% of bookings."
             " Grey = limited history. Full customer list is in the table.", color=grey, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    plt.show()
    plt.close(fig)


def build_customer_profiles():
    prepared = globals().get("CUSTOMER_TIMING")
    if not isinstance(prepared, dict) or prepared.get("frame") is None:
        raise RuntimeError("Run 01_booking_timing.py first, or run customer_booking_patterns_all_in_one.py.")
    settings = prepared["settings"]
    frame = prepared["frame"]
    included = frame.filter(F.col("coverage_status") == "Included")
    quantiles = F.percentile_approx("days_from_cutoff", [0.25, 0.5, 0.75], 10000)
    profile_frame = included.groupBy("service", "customer_key").agg(
        F.min("customer").alias("customer"), F.count("*").alias("bookings"),
        F.countDistinct("svvd").alias("voyages"), quantiles.alias("quantiles"),
        F.sum(F.when(F.col("days_from_cutoff") < 0, 1).otherwise(0)).alias("before_cutoff"),
        F.sum(F.when(F.col("days_from_cutoff") == 0, 1).otherwise(0)).alias("at_cutoff"),
        F.sum(F.when(F.col("days_from_cutoff") > 0, 1).otherwise(0)).alias("after_cutoff"),
        F.min("cutoff_us").alias("first_cutoff_us"), F.max("cutoff_us").alias("last_cutoff_us")
    )
    profiles = profile_frame.limit(100001).toPandas()
    if len(profiles) > 100000:
        raise RuntimeError("More than 100,000 customer-service profiles. Set SERVICES to a smaller list and rerun.")
    if profiles.empty:
        print("No bookings meet the comparison rules. See the coverage table; no groups or curves were fabricated.")
        return None
    profiles[["p25_day", "median_day", "p75_day"]] = pd.DataFrame(profiles.pop("quantiles").tolist(), index=profiles.index)
    profiles[["p25_day", "median_day", "p75_day"]] = profiles[["p25_day", "median_day", "p75_day"]].astype(float)
    profiles["middle_50pct_span_days"] = profiles.p75_day - profiles.p25_day
    profiles["after_cutoff_pct"] = 100.0 * profiles.after_cutoff / profiles.bookings

    # Split by voyage cutoff, keeping every booking on the same voyage in one period.
    voyage_times = included.groupBy("service", "svvd").agg(F.min("cutoff_us").alias("voyage_cutoff_us"))
    splits = voyage_times.groupBy("service").agg(F.percentile_approx("voyage_cutoff_us", 0.5, 10000).alias("split_us"))
    period_rows = (included.join(voyage_times, ["service", "svvd"])
                   .join(splits, ["service"])
                   .withColumn("period", F.when(F.col("voyage_cutoff_us") < F.col("split_us"), "Earlier").otherwise("Later")))
    halves = period_rows.groupBy("service", "customer_key", "period").agg(
        F.count("*").alias("period_bookings"), F.countDistinct("svvd").alias("period_voyages"),
        F.percentile_approx("days_from_cutoff", 0.5, 10000).alias("period_median")
    ).toPandas()
    halves["period_median"] = halves.period_median.astype(float)
    for period, prefix in [("Earlier", "earlier"), ("Later", "later")]:
        part = halves[halves.period == period].drop(columns="period").rename(columns={
            "period_bookings": f"{prefix}_bookings", "period_voyages": f"{prefix}_voyages",
            "period_median": f"{prefix}_median_day"})
        profiles = profiles.merge(part, on=["service", "customer_key"], how="left", validate="one_to_one")
    profiles["median_shift_days"] = profiles.later_median_day - profiles.earlier_median_day
    enough = ((profiles.earlier_bookings >= 5) & (profiles.later_bookings >= 5) &
              (profiles.earlier_voyages >= 2) & (profiles.later_voyages >= 2))
    profiles["history_check"] = np.where(
        ~enough, "Not enough history in both periods",
        np.where(profiles.median_shift_days.abs() <= STABILITY_SHIFT_DAYS,
                 "Similar median across periods", "Median changed across periods"))
    profiles, model_summary = assign_timing_groups(
        profiles, MIN_BOOKINGS, MIN_VOYAGES, MIN_CUSTOMERS_PER_GROUP, MAX_GROUPS, MIN_SILHOUETTE)
    profiles["usual_booking_time"] = profiles.median_day.map(describe_day)
    profiles = profiles.sort_values(["service", "group_order", "median_day", "customer_key"]).reset_index(drop=True)
    groups = (profiles.groupby(["service", "timing_group", "group_order", "group_note"], dropna=False)
              .agg(customers=("customer_key", "size"), bookings=("bookings", "sum"),
                   median_customer_day=("median_day", "median"),
                   median_customer_span_days=("middle_50pct_span_days", "median"))
              .reset_index().sort_values(["service", "group_order"]))
    service_coverage = (frame.groupBy("service", "coverage_status").count().toPandas()
                        .pivot(index="service", columns="coverage_status", values="count").fillna(0))
    service_coverage["bookings_with_year_assigned"] = service_coverage.drop(
        columns=["Booking time unresolved; year not assigned"], errors="ignore").sum(axis=1)
    service_coverage["included_pct_of_year_bookings"] = np.where(
        service_coverage.bookings_with_year_assigned > 0,
        100.0 * service_coverage.get("Included", 0) / service_coverage.bookings_with_year_assigned,
        np.nan)
    print("\nCustomer booking patterns")
    print(f"{len(profiles):,} customer-service profiles | {int(profiles.bookings.sum()):,} bookings | "
          f"{profiles.service.nunique():,} services")
    print(f"Grouping minimum: {MIN_BOOKINGS} bookings across {MIN_VOYAGES} voyages per customer and service.")
    print("Customer names are matched by spacing and case only; different aliases remain separate.")
    print("These are observed booking habits, not a prediction that a customer will or will not book.")
    print("\nService coverage")
    display(service_coverage.reset_index())
    print("\nTiming groups — group numbers belong to each service")
    display(groups.drop(columns="group_order").round(2))
    print("\nCustomer lookup")
    customer_columns = ["service", "customer", "timing_group", "bookings", "voyages",
                        "usual_booking_time", "p25_day", "median_day", "p75_day",
                        "before_cutoff", "at_cutoff", "after_cutoff", "after_cutoff_pct",
                        "history_check", "earlier_median_day", "later_median_day", "median_shift_days"]
    display(profiles[customer_columns].round(2))
    print("\nGroup selection")
    display(model_summary.round(3))

    # All services are calculated. The selector controls only the two displayed figures.
    profiles["eligible_for_grouping"] = profiles.timing_group != "Limited history"
    service_sizes = (profiles.groupby("service").agg(eligible_customers=("eligible_for_grouping", "sum"),
                                                   customers=("customer_key", "size"), bookings=("bookings", "sum"))
                     .sort_values(["eligible_customers", "customers", "bookings"], ascending=False))
    selected = str(CHART_SERVICE).strip().upper() if CHART_SERVICE else service_sizes.index[0]

    def show_service(service, customer=None):
        service = str(service).strip().upper()
        members = profiles[profiles.service == service]
        if members.empty:
            print("No usable profiles for this service. Available: " + ", ".join(service_sizes.index))
            return None
        daily = (included.filter(F.col("service") == service)
                 .groupBy("service", "customer_key", "day_from_cutoff").count()
                 .withColumnRenamed("count", "daily_bookings").limit(2000001).toPandas())
        if len(daily) > 2000000:
            raise RuntimeError("More than 2 million customer-day rows in this service; narrow the population before plotting.")
        membership = members[members.timing_group != "Limited history"]
        days = list(range(-settings["days_before"], settings["days_after"]))
        if membership.empty:
            curves = pd.DataFrame(columns=["timing_group", "day_from_cutoff", "bookings", "mean_customer_booking_pct"])
            print("This service has limited customer history. Customer windows are shown without forced groups.")
        else:
            curves = customer_weighted_curves(daily, membership, days)
        with plt.rc_context({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white"}):
            plot_customer_patterns(curves, members, service, settings["days_before"],
                                   settings["days_after"], customer, MAX_CUSTOMERS_ON_CHART)
        print(f"Charts: {service}. All services remain in the customer and group tables above.")
        if not curves.empty:
            print("\nDaily group counts and customer-weighted curve values")
            display(curves.round({"mean_customer_booking_pct": 3}))
        print("\nExact daily booking counts by customer")
        names = members[["service", "customer_key", "customer", "timing_group"]]
        table = daily.merge(names, on=["service", "customer_key"], validate="many_to_one")
        if customer:
            table = table[table.customer_key == " ".join(str(customer).split()).upper()]
        display(table[["service", "customer", "timing_group", "day_from_cutoff", "daily_bookings"]]
                .sort_values(["customer", "day_from_cutoff"]))
        return curves

    curves = show_service(selected, CHART_CUSTOMER)
    print("\nChange the service with show_customer_service('SERVICE_CODE').")
    print("Use show_customer_service('SERVICE_CODE', 'Customer name') to focus the customer chart and daily table.")
    print("No source tables were changed. Groups describe the stated window and available matched bookings.")
    return {"profiles": profiles, "groups": groups, "model_summary": model_summary,
            "coverage": service_coverage, "curves": curves, "show_service": show_service}


CUSTOMER_RESULTS = build_customer_profiles()
if CUSTOMER_RESULTS is not None:
    show_customer_service = CUSTOMER_RESULTS["show_service"]
