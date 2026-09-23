"""Synthetic checks for customer timing groups and notebook figures.

No Spark session, source data, or corporate connection is used. Run with:
    python -m unittest discover -s tests -p 'test_customer_groups.py' -v
"""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


NOTEBOOK = (Path(__file__).resolve().parents[1] / "notebooks" /
            "customer-booking-patterns" / "02_customer_groups_and_charts.py")
FUNCTIONS = {
    "assign_timing_groups", "describe_day", "customer_weighted_curves",
    "plot_customer_patterns",
}


def load_helpers():
    tree = ast.parse(NOTEBOOK.read_text())
    definitions = [node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    if {node.name for node in definitions} != FUNCTIONS:
        raise AssertionError("A required notebook helper is missing")
    namespace = {
        "np": np, "pd": pd, "plt": plt, "MaxNLocator": MaxNLocator,
        "KMeans": KMeans, "silhouette_score": silhouette_score,
    }
    exec(compile(ast.Module(body=definitions, type_ignores=[]),
                 str(NOTEBOOK), "exec"), namespace)
    return namespace


HELPERS = load_helpers()
assign_timing_groups = HELPERS["assign_timing_groups"]
customer_weighted_curves = HELPERS["customer_weighted_curves"]
plot_customer_patterns = HELPERS["plot_customer_patterns"]


def synthetic_profiles(centres=(-21.0, -7.0, 4.0), size=6, service="SERVICE_A"):
    rows = []
    for group, centre in enumerate(centres):
        for i in range(size):
            median = centre + 0.08 * (i - (size - 1) / 2)
            key = f"CUSTOMER {group}-{i}"
            rows.append({
                "service": service, "customer_key": key, "customer": key.title(),
                "bookings": 20 + i, "voyages": 3 + i % 2,
                "p25_day": median - 1, "median_day": median,
                "p75_day": median + 1,
            })
    return pd.DataFrame(rows)


class TimingGroupsTest(unittest.TestCase):
    def test_limited_history_is_not_forced_into_a_group(self):
        profiles = synthetic_profiles(centres=(-7,), size=3)
        profiles.loc[0, "bookings"] = 19
        profiles.loc[1, "voyages"] = 2
        profiles.loc[2, ["bookings", "voyages"]] = [20, 3]
        assigned, summary = assign_timing_groups(profiles)
        self.assertEqual(assigned.timing_group.tolist(),
                         ["Limited history", "Limited history", "G1"])
        self.assertEqual(summary.iloc[0].customers_for_grouping, 1)
        self.assertEqual(summary.iloc[0].groups, 1)

    def test_no_eligible_customers_has_no_fabricated_groups(self):
        profiles = synthetic_profiles(size=2)
        profiles["bookings"] = 3
        assigned, summary = assign_timing_groups(profiles)
        self.assertTrue((assigned.timing_group == "Limited history").all())
        self.assertEqual(summary.iloc[0].groups, 0)
        self.assertEqual(summary.iloc[0].customers_for_grouping, 0)

    def test_identical_profiles_remain_one_group(self):
        profiles = synthetic_profiles(centres=(-7,), size=20)
        profiles[["p25_day", "median_day", "p75_day"]] = [-9.0, -7.0, -5.0]
        assigned, summary = assign_timing_groups(profiles)
        self.assertEqual(set(assigned.timing_group), {"G1"})
        self.assertEqual(summary.iloc[0].groups, 1)
        self.assertIsNone(summary.iloc[0].silhouette)
        self.assertEqual(summary.iloc[0].decision,
                         "No clear separation into smaller groups")

    def test_separate_patterns_receive_ordered_groups(self):
        profiles = synthetic_profiles()
        assigned, summary = assign_timing_groups(profiles)
        self.assertEqual(summary.iloc[0].groups, 3)
        self.assertGreater(summary.iloc[0].silhouette, 0.9)
        self.assertEqual(assigned.timing_group.tolist(),
                         ["G1"] * 6 + ["G2"] * 6 + ["G3"] * 6)
        self.assertGreaterEqual(assigned.groupby("timing_group").size().min(), 5)

    def test_service_grouping_is_independent(self):
        a = synthetic_profiles()
        b = synthetic_profiles(centres=(9,), size=12, service="SERVICE_B")
        b[["p25_day", "median_day", "p75_day"]] = [8.0, 9.0, 10.0]
        combined = pd.concat([a, b], ignore_index=True)
        assigned, summary = assign_timing_groups(combined)
        self.assertEqual(summary.set_index("service")["groups"].to_dict(),
                         {"SERVICE_A": 3, "SERVICE_B": 1})
        self.assertEqual(assigned[assigned.service == "SERVICE_A"].timing_group.tolist(),
                         ["G1"] * 6 + ["G2"] * 6 + ["G3"] * 6)
        self.assertEqual(set(assigned[assigned.service == "SERVICE_B"].timing_group),
                         {"G1"})

    def test_booking_volume_is_not_a_clustering_feature(self):
        profiles = synthetic_profiles()
        original, _ = assign_timing_groups(profiles)
        changed_volume = profiles.copy()
        changed_volume["bookings"] = [20, 200000, 31, 720, 5000, 55] * 3
        changed_volume["voyages"] = [3, 100, 4, 9, 88, 6] * 3
        assigned, _ = assign_timing_groups(changed_volume)
        self.assertEqual(assigned.timing_group.tolist(), original.timing_group.tolist())

    def test_results_are_repeatable_and_input_is_preserved(self):
        profiles = synthetic_profiles()
        before = profiles.copy(deep=True)
        first, first_summary = assign_timing_groups(profiles)
        second, second_summary = assign_timing_groups(profiles)
        shuffled, _ = assign_timing_groups(profiles.sample(frac=1, random_state=17))
        pd.testing.assert_frame_equal(first, second)
        pd.testing.assert_frame_equal(first_summary, second_summary)
        pd.testing.assert_frame_equal(profiles, before)
        pd.testing.assert_series_equal(first.timing_group.sort_index(),
                                       shuffled.timing_group.sort_index())


class CustomerCurvesTest(unittest.TestCase):
    def setUp(self):
        self.membership = pd.DataFrame([
            {"service": "A", "customer_key": "LARGE", "timing_group": "G1", "bookings": 100},
            {"service": "A", "customer_key": "SMALL", "timing_group": "G1", "bookings": 20},
            {"service": "A", "customer_key": "LATE", "timing_group": "G2", "bookings": 40},
        ])
        self.daily = pd.DataFrame([
            {"service": "A", "customer_key": "LARGE", "day_from_cutoff": -2, "daily_bookings": 100},
            {"service": "A", "customer_key": "SMALL", "day_from_cutoff": -1, "daily_bookings": 20},
            {"service": "A", "customer_key": "LATE", "day_from_cutoff": 1, "daily_bookings": 40},
            {"service": "B", "customer_key": "LARGE", "day_from_cutoff": -2, "daily_bookings": 999},
            {"service": "A", "customer_key": "UNCLASSIFIED", "day_from_cutoff": 0, "daily_bookings": 99},
        ])
        self.days = [-2, -1, 0, 1]

    def test_every_day_is_present_and_customers_have_equal_weight(self):
        curves = customer_weighted_curves(self.daily, self.membership, self.days)
        early = curves[curves.timing_group == "G1"]
        self.assertEqual(early.day_from_cutoff.tolist(), self.days)
        self.assertEqual(early.bookings.tolist(), [100, 20, 0, 0])
        np.testing.assert_allclose(early.mean_customer_booking_pct, [50, 50, 0, 0])
        self.assertEqual(len(curves), 2 * len(self.days))
        np.testing.assert_allclose(curves.groupby("timing_group").mean_customer_booking_pct.sum(),
                                   [100, 100])

    def test_other_services_and_unclassified_customers_do_not_duplicate_counts(self):
        curves = customer_weighted_curves(self.daily, self.membership, self.days)
        self.assertEqual(int(curves.bookings.sum()), 160)
        self.assertFalse(curves.duplicated(["timing_group", "day_from_cutoff"]).any())

    def test_duplicate_membership_is_rejected(self):
        duplicated = pd.concat([self.membership, self.membership.iloc[[0]]], ignore_index=True)
        with self.assertRaises(pd.errors.MergeError):
            customer_weighted_curves(self.daily, duplicated, self.days)


class ChartRenderingTest(unittest.TestCase):
    def test_two_required_figures_render_from_synthetic_rows(self):
        profiles = synthetic_profiles(centres=(-21, -7), size=6)
        profiles, _ = assign_timing_groups(profiles)
        daily = profiles[["service", "customer_key", "bookings", "median_day"]].copy()
        daily["day_from_cutoff"] = np.floor(daily.pop("median_day")).astype(int)
        daily = daily.rename(columns={"bookings": "daily_bookings"})
        days = list(range(-28, 14))
        curves = customer_weighted_curves(daily, profiles, days)
        figures = []
        with tempfile.TemporaryDirectory() as folder:
            def capture():
                fig = plt.gcf()
                output = Path(folder) / f"chart-{len(figures) + 1}.png"
                fig.savefig(output, dpi=100)
                figures.append((fig, output))

            with patch.object(plt, "show", side_effect=capture):
                plot_customer_patterns(curves, profiles, "SERVICE_A", 28, 14)
            self.assertEqual(len(figures), 2)
            self.assertEqual(len(figures[0][0].axes), 2)
            self.assertEqual(len(figures[1][0].axes), 1)
            self.assertEqual(len(figures[1][0].axes[0].get_yticklabels()), len(profiles))
            for _, output in figures:
                image = plt.imread(output)
                self.assertGreater(output.stat().st_size, 10000)
                self.assertGreater(image.shape[0], 250)
                self.assertGreater(float(image[..., :3].std()), 0.03)
        self.assertEqual(plt.get_fignums(), [])

    def test_limited_history_only_has_customer_windows_without_group_curve(self):
        profiles = synthetic_profiles(centres=(-7,), size=3)
        profiles["bookings"] = 2
        profiles, _ = assign_timing_groups(profiles)
        curves = pd.DataFrame(columns=["timing_group", "day_from_cutoff", "bookings",
                                       "mean_customer_booking_pct"])
        figures = []
        with patch.object(plt, "show", side_effect=lambda: figures.append(plt.gcf())):
            plot_customer_patterns(curves, profiles, "SERVICE_A", 28, 14)
        self.assertEqual(len(figures), 1)
        self.assertEqual(len(figures[0].axes[0].get_yticklabels()), 3)


if __name__ == "__main__":
    unittest.main()
