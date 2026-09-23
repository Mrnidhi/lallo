"""Synthetic plotting checks; no Spark or corporate source access."""

import ast
from pathlib import Path
import textwrap
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


SOURCE = (Path(__file__).resolve().parents[1] /
          "notebooks/customer-booking-patterns/group_space_chart_helpers.py")


def load_chart_helpers():
    tree = ast.parse(SOURCE.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    namespace = {"textwrap": textwrap, "plt": plt, "Line2D": Line2D,
                 "MaxNLocator": MaxNLocator, "np": np, "pd": pd}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


HELPERS = load_chart_helpers()


class GroupSpaceCharts(unittest.TestCase):
    def setUp(self):
        self.show_patch = patch.object(plt, "show")
        self.show = self.show_patch.start()

    def tearDown(self):
        self.show_patch.stop()
        plt.close("all")

    def summary(self, count=1, timed=True):
        return pd.DataFrame([
            {"customer": f"Example Customer {i}", "customer_key": f"EXAMPLE CUSTOMER {i}",
             "service": "S1" if i < 15 else "S2", "timing_group": f"G{i % 3 + 1}",
             "bookings": 30 + i, "p25_day": -10, "median_day": -7, "p75_day": -4,
             "request_timed_count": 2 if timed else 0,
             "request_p25_day": -4 if timed else np.nan,
             "request_median_day": -2 if timed else np.nan,
             "request_p75_day": 0 if timed else np.nan,
             "request_count": 3, "min_extra_teu": 1, "median_extra_teu": 2, "max_extra_teu": 5,
             "min_requested_total_teu": 4, "median_requested_total_teu": 6,
             "max_requested_total_teu": 11}
            for i in range(count)
        ])

    def detail(self, daily, events=None, before=3, after=2):
        if events is None:
            events = pd.DataFrame(columns=["days_from_cutoff", "extra_teu", "audit_id"])
        return HELPERS["plot_group_space_customer"](
            daily, events, "Example Customer", "S1", "G2", before, after)

    def booking_lines(self, ax):
        return [line for line in ax.lines if line.get_color() == "#203D62"]

    def test_ast_functions_execute_with_only_declared_plot_dependencies(self):
        tree = ast.parse(SOURCE.read_text())
        self.assertTrue(all(isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Expr))
                            for node in tree.body))
        for node in tree.body:
            if isinstance(node, ast.Expr):
                self.assertIsInstance(node.value, ast.Constant)
        self.assertTrue(callable(HELPERS["plot_group_space_overview"]))
        self.assertTrue(callable(HELPERS["plot_group_space_customer"]))

    def test_missing_days_are_zero_with_duplicate_daily_rows_combined(self):
        fig = self.detail(pd.DataFrame({"day_from_cutoff": [-2, -2, 1], "bookings": [3, 4, 2]}))[0]
        line = self.booking_lines(fig.axes[0])[0]
        np.testing.assert_array_equal(line.get_xdata(), [-3, -2, -1, 0, 1])
        np.testing.assert_array_equal(line.get_ydata(), [0, 7, 0, 0, 2])
        self.assertGreater(fig.axes[0].get_ylim()[1], 7)
        self.assertNotIn(fig.number, plt.get_fignums())

    def test_empty_daily_input_does_not_imply_zero_demand(self):
        fig, request_fig = self.detail(pd.DataFrame(columns=["day_from_cutoff", "bookings"]))
        self.assertEqual(self.booking_lines(fig.axes[0]), [])
        self.assertTrue(any("No usable booking records" in t.get_text() for t in fig.axes[0].texts))
        self.assertEqual(len(request_fig.axes[0].collections), 0)

    def test_outside_window_only_does_not_create_false_zero_curve(self):
        fig = self.detail(pd.DataFrame({"day_from_cutoff": [-10, 2], "bookings": [5, 9]}))[0]
        self.assertEqual(self.booking_lines(fig.axes[0]), [])

    def test_missing_request_timing_has_no_red_marker(self):
        fig = HELPERS["plot_group_space_overview"](self.summary(timed=False), 28, 14)[1]
        timeline = fig.axes[1]
        self.assertEqual(len(timeline.collections), 0)
        self.assertTrue(any("Request timing unavailable" in t.get_text() for t in timeline.texts))
        self.assertTrue(any("0 / 3" in t.get_text() for t in fig.axes[2].texts))

    def test_request_event_precision_and_quantities_are_not_daily_summed(self):
        events = pd.DataFrame({"days_from_cutoff": [-1.75, -1.5, 1.25, 2.0],
                               "extra_teu": [2, 3, 8, 100], "audit_id": [1, 2, 3, 4]})
        fig = self.detail(pd.DataFrame({"day_from_cutoff": [-1], "bookings": [1]}), events)[1]
        dots = fig.axes[0].collections[-1]
        np.testing.assert_allclose(dots.get_offsets(), [[-1.75, 2], [-1.5, 3], [1.25, 8]])
        self.assertGreater(fig.axes[0].get_ylim()[1], 8)
        self.assertLess(fig.axes[0].get_ylim()[1], 100)
        self.assertTrue(any("median 3 / max 8" in t.get_text() for t in fig.texts))

    def test_overview_pagination_keeps_all_profiles_and_closes_figures(self):
        figures = HELPERS["plot_group_space_overview"](self.summary(count=25), 28, 14, 12)
        self.assertEqual(len(figures), 6)
        self.assertEqual([len(fig.axes[0].texts) for fig in figures], [12, 12, 1, 12, 12, 1])
        labels = "\n".join(text.get_text() for fig in figures for text in fig.axes[0].texts)
        self.assertIn("S1 · G1", labels)
        self.assertIn("S2 · G1", labels)
        self.assertEqual(plt.get_fignums(), [])
        self.assertEqual(self.show.call_count, 6)

    def test_invalid_fractional_daily_counts_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "integer days"):
            self.detail(pd.DataFrame({"day_from_cutoff": [-1.5], "bookings": [1]}))

    def test_booking_and_request_series_are_in_separate_figures(self):
        events = pd.DataFrame({"days_from_cutoff": [-1.5], "extra_teu": [3], "audit_id": [1]})
        detail = self.detail(pd.DataFrame({"day_from_cutoff": [-1], "bookings": [4]}), events)
        self.assertEqual(len(detail), 2)
        self.assertTrue(all(len(fig.axes) == 1 for fig in detail))
        self.assertNotEqual(detail[0].axes[0].get_title(loc="left"),
                            detail[1].axes[0].get_title(loc="left"))
        self.assertEqual(len(detail[0].axes[0].collections), 0)
        self.assertEqual(self.booking_lines(detail[1].axes[0]), [])
        np.testing.assert_allclose(detail[1].axes[0].collections[-1].get_facecolors()[0][:3],
                                   matplotlib.colors.to_rgb("#D10A2C"))
        overview = HELPERS["plot_group_space_overview"](self.summary(), 28, 14)
        self.assertEqual(len(overview), 2)
        self.assertEqual(overview[0]._suptitle.get_text(), "Customer booking timing")
        self.assertEqual(overview[1]._suptitle.get_text(), "Requested-space timing and amounts")
        for fig, color in zip(overview, ("#203D62", "#D10A2C")):
            self.assertEqual(len(fig.axes[1].collections), 1)
            np.testing.assert_allclose(fig.axes[1].collections[0].get_facecolors()[0][:3],
                                       matplotlib.colors.to_rgb(color))


if __name__ == "__main__":
    unittest.main()
