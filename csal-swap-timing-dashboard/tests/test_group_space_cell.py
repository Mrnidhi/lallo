"""The distributed code must be usable as a single paste-ready Python cell."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "notebooks/csal-group-customer-space-timeline.py"


class PasteReadyCell(unittest.TestCase):
    def test_current_helpers_are_included_without_cache_calls(self):
        tree = ast.parse(TARGET.read_text())
        functions = {n.name: ast.dump(n, include_attributes=False) for n in tree.body
                     if isinstance(n, ast.FunctionDef)}
        for filename in ("group_space_chart_helpers.py", "group_space_timeline_core.py"):
            source = ROOT / "notebooks/customer-booking-patterns" / filename
            for node in ast.parse(source.read_text()).body:
                if isinstance(node, ast.FunctionDef):
                    self.assertEqual(functions[node.name], ast.dump(node, include_attributes=False))
        forbidden = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute)
                     and n.func.attr in {"cache", "persist", "unpersist"}]
        self.assertEqual(forbidden, [])

    def test_utc_confirmation_and_no_local_helper_imports(self):
        tree = ast.parse(TARGET.read_text())
        settings = {n.targets[0].id: n.value.value for n in tree.body
                    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                    and isinstance(n.value, ast.Constant)}
        self.assertEqual(settings["AUDIT_TIMEZONE"], "UTC")
        self.assertEqual(settings["TOP_CUSTOMERS"], 25)
        self.assertFalse(settings["REBUILD_GROUPS"])
        imported = {n.module for n in tree.body if isinstance(n, ast.ImportFrom)}
        self.assertFalse(any("group_space" in (module or "") for module in imported))
        self.assertTrue(any(isinstance(n, ast.Import) and any(a.name == "textwrap" for a in n.names)
                            for n in tree.body))


if __name__ == "__main__":
    unittest.main()
