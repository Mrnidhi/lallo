"""Separate charts for customer bookings and recorded requested-space increases."""

import textwrap

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


def _group_space_number(value):
    if pd.isna(value):
        return "—"
    number = float(value)
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.1f}"


def _group_space_range(row, prefix):
    return " / ".join(
        _group_space_number(row.get(f"{part}_{prefix}", np.nan))
        for part in ("min", "median", "max")
    )


def _group_space_style(ax):
    ax.set_facecolor("white")
    ax.spines[["top", "right"]].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D5DCE3")
    ax.tick_params(colors="#46566A", labelsize=9)
    ax.grid(axis="x", color="#E8EDF2", linewidth=0.7)
    ax.set_axisbelow(True)


def plot_group_space_overview(summary, before, after, rows_per_page=12):
    """Display separate booking and requested-space figures; return all figures.

    Ordering is all booking pages, then all requested-space pages. Customer rows
    have the same order in both sets. Quantity statistics use all qualifying
    increases; request timing uses only increases with usable cutoff timing.
    """
    if rows_per_page < 1 or before < 0 or after <= 0:
        raise ValueError("Use rows_per_page >= 1, before >= 0 and after > 0.")
    required = {"customer", "service", "timing_group", "bookings", "p25_day",
                "median_day", "p75_day", "request_timed_count", "request_count"}
    missing = required.difference(summary.columns)
    if missing:
        raise ValueError("Missing summary columns: " + ", ".join(sorted(missing)))
    navy, red = "#203D62", "#D10A2C"
    ordered = summary.copy()
    ordered["_group_order"] = pd.to_numeric(
        ordered["timing_group"].astype(str).str.extract(r"(\d+)", expand=False),
        errors="coerce",
    ).fillna(999)
    ordered = ordered.sort_values(
        ["service", "_group_order", "median_day", "bookings", "customer"],
        ascending=[True, True, True, False, True], kind="stable",
    )
    pages = max(1, int(np.ceil(len(ordered) / rows_per_page)))
    figures = []
    for kind in ("booking", "request"):
        is_request = kind == "request"
        title = "Requested-space timing and amounts" if is_request else "Customer booking timing"
        color, marker = (red, "D") if is_request else (navy, "o")
        for page_index in range(pages):
            page = ordered.iloc[page_index * rows_per_page:(page_index + 1) * rows_per_page]
            count = len(page)
            if not count:
                fig, ax = plt.subplots(figsize=(12, 3), facecolor="white")
                ax.axis("off")
                ax.set_title(title, loc="left", color=navy, fontweight="bold")
                ax.text(0.5, 0.5, "No customers meet the selected booking criteria.",
                        transform=ax.transAxes, ha="center", color="#687786", fontsize=11)
                plt.show()
                plt.close(fig)
                figures.append(fig)
                continue
            height = 0.82 * count + 3.2
            fig = plt.figure(figsize=(17, height), facecolor="white")
            widths = [3.5, 5.4, 3.5] if is_request else [3.5, 8.9]
            grid = fig.add_gridspec(1, len(widths), width_ratios=widths,
                                   left=0.025, right=0.985, bottom=1.05 / height,
                                   top=1 - 1.5 / height, wspace=0.04)
            labels_ax, ax = [fig.add_subplot(grid[0, n]) for n in range(2)]
            values_ax = fig.add_subplot(grid[0, 2]) if is_request else None
            for panel in fig.axes:
                panel.set_ylim(count - 0.5, -0.5)
            for panel in [labels_ax] + ([values_ax] if is_request else []):
                panel.set_xlim(0, 1)
                panel.axis("off")
            _group_space_style(ax)
            ax.spines["left"].set_visible(False)
            ax.set_yticks([])
            ax.set_xlim(-before, after)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.axvline(0, color="#687786", linewidth=1.2, linestyle="--", zorder=1)
            ax.set_xlabel("Days from TCR cutoff  ·  0 = cutoff", fontsize=10, color=navy, labelpad=10)
            labels_ax.set_title("Customer / service / group", loc="left", fontsize=10,
                                color=navy, fontweight="bold", pad=14)
            if is_request:
                values_ax.set_title("Added TEU; requested total TEU\nMin / median / max", loc="left",
                                    fontsize=10, color=navy, fontweight="bold", pad=14)
            for position, (_, row) in enumerate(page.iterrows()):
                name = textwrap.fill(str(row["customer"]), width=43, max_lines=3, placeholder="…")
                label = f"{name}\n{row['service']} · {row['timing_group']}"
                if not is_request:
                    label += f" · {_group_space_number(row['bookings'])} bookings"
                labels_ax.text(0, position, label, ha="left", va="center",
                               fontsize=9, color=navy, linespacing=1.35)
                if position % 2 == 0:
                    ax.axhspan(position - 0.48, position + 0.48, color="#F7F9FB", zorder=0)
                prefix = "request_" if is_request else ""
                quantiles = [row.get(f"{prefix}{part}_day", np.nan)
                             for part in ("p25", "median", "p75")]
                timed_count = row.get("request_timed_count", 0)
                enough = not is_request or (pd.notna(timed_count) and float(timed_count) > 0)
                if enough and all(pd.notna(value) for value in quantiles):
                    lower, middle, upper = map(float, quantiles)
                    ax.plot([lower, upper], [position, position], color=color, linewidth=3,
                            solid_capstyle="round", zorder=3)
                    ax.scatter([middle], [position], s=28, color=color, marker=marker, zorder=4)
                else:
                    message = "Request timing unavailable" if is_request else "Booking timing unavailable"
                    ax.text(0.02, position, message, transform=ax.get_yaxis_transform(),
                            fontsize=9, color="#687786", va="center")
                if is_request:
                    quantities = (
                        f"Added: {_group_space_range(row, 'extra_teu')}\n"
                        f"Total: {_group_space_range(row, 'requested_total_teu')}\n"
                        f"Timed / all increases: {_group_space_number(row['request_timed_count'])}"
                        f" / {_group_space_number(row['request_count'])}"
                    )
                    values_ax.text(0.03, position, quantities, fontsize=9, va="center",
                                   color=navy, linespacing=1.4)
            fig.suptitle(title, x=0.025, y=1 - 0.18 / height, ha="left", color=navy,
                         fontsize=16, fontweight="bold")
            legend = [Line2D([0], [0], color=color, marker=marker, linewidth=3,
                            label="Middle 50% and median of recorded increases" if is_request
                            else "Middle 50% and median of booking days")]
            fig.legend(handles=legend, loc="upper left", bbox_to_anchor=(0.022, 1 - 0.65 / height),
                       frameon=False, fontsize=10)
            fig.text(0.985, 1 - 0.32 / height, f"Page {page_index + 1} of {pages}",
                     ha="right", color="#687786", fontsize=9)
            note = (
                "Groups are defined within each service. Timing uses only increases with usable cutoff timing in the window; "
                "TEU statistics use all qualifying recorded increases.\n"
                "Request dates use current cutoff mappings, not reconstructed historical cutoffs. "
                "Requested-TEU edits do not establish that the customer submitted a request."
                if is_request else
                "Groups are defined within each service. Each marker is a customer/service median; the line covers the middle 50% of booking days.\n"
                "Timing uses only eligible bookings in the selected window and available route/cutoff records; historical route changes are not reconstructed."
            )
            fig.text(0.025, 0.17 / height, note, fontsize=8.5, color="#687786", linespacing=1.6)
            plt.show()
            plt.close(fig)
            figures.append(fig)
    return figures


def _group_space_detail_figure(customer, service, group, before, after, title):
    fig, ax = plt.subplots(figsize=(12, 5.4), facecolor="white")
    fig.subplots_adjust(top=0.69, bottom=0.25, left=0.095, right=0.97)
    fig.suptitle(textwrap.fill(str(customer), width=78), x=0.095, y=0.97,
                 ha="left", fontsize=15, fontweight="bold", color="#203D62")
    fig.text(0.095, 0.79, f"{service} · {group} · TCR cutoff = day 0", fontsize=10, color="#687786")
    _group_space_style(ax)
    ax.grid(axis="y", color="#EDF0F4", linewidth=0.7)
    ax.axvline(0, color="#687786", linestyle="--", linewidth=1.2)
    ax.set_xlim(-before, after)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title, loc="left", color="#203D62", fontweight="bold", fontsize=12, pad=14)
    ax.set_xlabel("Days from TCR cutoff  ·  negative = before  ·  positive = after",
                   color="#203D62", fontsize=10, labelpad=10)
    return fig, ax


def plot_group_space_customer(daily, events, customer, service, group, before, after):
    """Return two separately displayed figures: bookings, then requested space."""
    if before < 0 or after <= 0:
        raise ValueError("Use before >= 0 and after > 0.")
    navy, red = "#203D62", "#D10A2C"
    bookings = daily.copy()
    if not bookings.empty:
        bookings["day_from_cutoff"] = pd.to_numeric(bookings["day_from_cutoff"], errors="coerce")
        bookings["bookings"] = pd.to_numeric(bookings["bookings"], errors="coerce")
        bookings = bookings.loc[bookings["day_from_cutoff"].ge(-before)
                                & bookings["day_from_cutoff"].lt(after)].dropna(
                                    subset=["day_from_cutoff", "bookings"])
        bookings = bookings.groupby("day_from_cutoff", as_index=False)["bookings"].sum()
        if not bookings.empty:
            if not bookings["day_from_cutoff"].mod(1).eq(0).all():
                raise ValueError("Daily booking counts must use integer days from cutoff.")
            bookings = bookings.set_index("day_from_cutoff").reindex(
                pd.Index(range(-int(before), int(after)), name="day_from_cutoff"), fill_value=0,
            ).reset_index()
    requests = events.copy()
    if not requests.empty:
        requests["days_from_cutoff"] = pd.to_numeric(requests["days_from_cutoff"], errors="coerce")
        requests["extra_teu"] = pd.to_numeric(requests["extra_teu"], errors="coerce")
        requests = requests.loc[requests["days_from_cutoff"].ge(-before)
                                & requests["days_from_cutoff"].lt(after)
                                & requests["extra_teu"].gt(0)].dropna(
                                    subset=["days_from_cutoff", "extra_teu"])

    booking_fig, booking_ax = _group_space_detail_figure(
        customer, service, group, before, after, "When bookings are created")
    if bookings.empty:
        booking_ax.text(0.5, 0.5, "No usable booking records in this window.",
                        transform=booking_ax.transAxes, ha="center", color="#687786")
    else:
        booking_ax.plot(bookings["day_from_cutoff"], bookings["bookings"],
                        color=navy, linewidth=1.7, marker="o", markersize=2.5)
    booking_ax.set_ylabel("Bookings per day", color=navy, fontsize=10)
    booking_ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    booking_ax.set_ylim(0, max(1.0, float(bookings["bookings"].max()) * 1.15) if not bookings.empty else 1)
    booking_fig.text(0.095, 0.07,
                     "Daily counts use eligible bookings in the selected cutoff window.\n"
                     "Routes and cutoffs reflect available records; historical route changes are not reconstructed.",
                     color="#687786", fontsize=8.5, linespacing=1.6)
    plt.show()
    plt.close(booking_fig)

    request_fig, request_ax = _group_space_detail_figure(
        customer, service, group, before, after, "Recorded increases to requested space")
    if requests.empty:
        request_ax.text(0.5, 0.5, "No requested-space increases with usable cutoff timing.",
                        transform=request_ax.transAxes, ha="center", color="#687786")
    else:
        request_ax.vlines(requests["days_from_cutoff"], 0, requests["extra_teu"],
                          color=red, linewidth=0.8, alpha=0.35)
        request_ax.scatter(requests["days_from_cutoff"], requests["extra_teu"],
                           color=red, s=32, alpha=0.8, zorder=3)
        amount = requests["extra_teu"]
        stats = (f"{len(requests):,} timed increases · Added TEU: "
                 f"min {_group_space_number(amount.min())} / "
                 f"median {_group_space_number(amount.median())} / "
                 f"max {_group_space_number(amount.max())}")
        request_fig.text(0.095, 0.125, stats, color=navy, fontsize=9)
    request_ax.set_ylabel("Added TEU per recorded edit", color=navy, fontsize=10)
    request_ax.set_ylim(0, max(1.0, float(requests["extra_teu"].max()) * 1.15) if not requests.empty else 1)
    request_fig.text(0.095, 0.055,
                     "Each dot is one recorded increase; overlapping dots may hide multiple edits. "
                     "Requested-TEU edits do not establish customer submission.\n"
                     "Request timing uses current cutoff mappings, not reconstructed historical cutoffs.",
                     color="#687786", fontsize=8.5, linespacing=1.6)
    plt.show()
    plt.close(request_fig)
    return [booking_fig, request_fig]
