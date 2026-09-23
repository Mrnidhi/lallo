"""Keep the one-cell deliverable in sync with the independently runnable parts."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "notebooks/customer-booking-patterns"


class CombinedCell(unittest.TestCase):
    def test_combined_cell_contains_the_two_current_parts(self):
        expected = []
        for name in ("01_booking_timing.py", "02_customer_groups_and_charts.py"):
            expected.extend(ast.parse((ROOT / name).read_text()).body)
        combined = ast.parse((ROOT / "customer_booking_patterns_all_in_one.py").read_text()).body
        self.assertIsInstance(combined[0], ast.Try)
        self.assertEqual([ast.dump(node) for node in combined[1:]],
                         [ast.dump(node) for node in expected])


if __name__ == "__main__":
    unittest.main()
