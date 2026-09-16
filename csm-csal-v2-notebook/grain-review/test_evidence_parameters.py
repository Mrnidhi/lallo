"""Exercise the copy guide's parameter setup without Databricks or corporate data."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


HERE = Path(__file__).resolve().parent
GUIDE = (HERE / "TEN_EVIDENCE_COPY_CELLS.md").read_text()
SETUP, BIND_ARGS = re.findall(r"```python\n(.*?)\n```", GUIDE, re.S)


class Widgets:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def getAll(self):
        return dict(self.values)

    def get(self, name):
        return self.values[name]

    def text(self, name, default):
        if name in self.values:
            raise AssertionError(f"Setup tried to overwrite {name}")
        self.values[name] = default


class EvidenceParameterTests(unittest.TestCase):
    def setup_parameters(self, values=None):
        widgets = Widgets(values)
        namespace = {"dbutils": SimpleNamespace(widgets=widgets)}
        with redirect_stdout(StringIO()):
            exec(SETUP, namespace)
        return widgets, namespace

    def test_every_compact_and_copy_marker_has_a_binding(self):
        widgets, namespace = self.setup_parameters()
        pack = (HERE / "TEN_EVIDENCE_SQL_PACK.sql").read_text()
        markers = set(re.findall(r"(?<!:):([a-z][a-z_]+)", pack))
        self.assertEqual(markers, set(namespace["evidence_parameter_defaults"]))
        cells = [sql for sql in re.findall(r"```sql\n(.*?)\n```", GUIDE, re.S)
                 if re.search(r"-- E(?:0[1-9]|10):", sql)]
        self.assertEqual(len(cells), 10)
        for sql in cells:
            self.assertEqual(set(re.findall(r"(?<!:):([a-z][a-z_]+)", sql)),
                             markers - {"evidence_id"})
        for name in markers:
            if name.endswith("_confirmed"):
                self.assertEqual(widgets.get(name), "0")
        self.assertEqual(widgets.get("agent_answer_value"), "")
        self.assertEqual(widgets.get("independent_raw_reference_total"), "")

    def test_existing_values_survive_repeated_setup(self):
        existing = {"report_month": "Test month", "gold_version": "12",
                    "upstream_version": "0", "agent_answer_value": "123",
                    "identity_rule_confirmed": "1", "metric_rule_confirmed": "",
                    "lineage_alignment_confirmed": "invalid", "unrelated": "keep"}
        widgets, namespace = self.setup_parameters(existing)
        with redirect_stdout(StringIO()):
            exec(SETUP, namespace)
        for name, value in existing.items():
            self.assertEqual(widgets.get(name), value)
        self.assertEqual(widgets.get("raw_source_validation_confirmed"), "0")

    def test_python_args_include_missing_flag_and_refresh_widget_values(self):
        widgets, namespace = self.setup_parameters(
            {"report_month": "Test month", "gold_version": "12", "upstream_version": "0"})
        exec(BIND_ARGS, namespace)
        self.assertEqual(namespace["evidence_args"]["gold_version"], 12)
        self.assertEqual(namespace["evidence_args"]["upstream_version"], 0)
        self.assertEqual(namespace["evidence_args"]["raw_source_validation_confirmed"], "0")
        widgets.values["agent_answer_value"] = "456"
        exec(BIND_ARGS, namespace)
        self.assertEqual(namespace["evidence_args"]["agent_answer_value"], "456")

    def test_month_and_versions_must_be_provided_without_guessing(self):
        widgets, namespace = self.setup_parameters()
        for name in ("report_month", "gold_version", "upstream_version"):
            self.assertEqual(widgets.get(name), "")
        with self.assertRaisesRegex(ValueError, "report_month"):
            exec(BIND_ARGS, namespace)
        widgets.values["report_month"] = "Test month"
        for name in ("gold_version", "upstream_version"):
            widgets.values.update(gold_version="0", upstream_version="0")
            for invalid in ("", "-1", "12.5", "latest", "1e2"):
                widgets.values[name] = invalid
                with self.subTest(name=name, value=invalid):
                    with self.assertRaisesRegex(ValueError, name):
                        exec(BIND_ARGS, namespace)


if __name__ == "__main__":
    unittest.main()
