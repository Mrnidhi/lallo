# Cell 11 | Test the scorer with synthetic records
# Checks numbers, NULLs, row order, aliases and missing evidence. No source data.

V2_SCORING_SELF_TESTS_PASSED = False
_v2_test_count = 0


def _v2_expect(label, expected_status, expected_rows, actual_rows,
               columns=None, numeric_precision=None, aliases=None, ordered=True):
    global _v2_test_count
    outcome = score_section(
        expected_rows, actual_rows,
        ["id", "value"] if columns is None else columns,
        {"value": None} if numeric_precision is None else numeric_precision,
        {} if aliases is None else aliases,
        ordered=ordered,
    )
    assert outcome["status"] == expected_status, f"{label}: {outcome}"
    _v2_test_count += 1
    return outcome


_v2_base = [{"id": "synthetic", "value": Decimal("12.00")}]
# Numbers: exact comparison, declared rounding, invalid values and NULLs.
_v2_expect("Exact numeric representations", "CORRECT", _v2_base,
           [{"id": "synthetic", "value": "12"}])
_v2_expect("Exact TEU retains fractional differences", "INCORRECT", _v2_base,
           [{"id": "synthetic", "value": "12.000001"}])
_v2_expect("Half-up rounding", "CORRECT",
           [{"id": "synthetic", "value": "1.235"}],
           [{"id": "synthetic", "value": "1.24"}], numeric_precision={"value": 2})
_v2_expect("Negative half-up rounding", "CORRECT",
           [{"id": "synthetic", "value": "-1.235"}],
           [{"id": "synthetic", "value": "-1.24"}], numeric_precision={"value": 2})
_v2_expect("Six-place comparison", "CORRECT",
           [{"id": "synthetic", "value": "1.1234565"}],
           [{"id": "synthetic", "value": "1.123457"}], numeric_precision={"value": 6})
_v2_expect("Six-place difference remains visible", "INCORRECT",
           [{"id": "synthetic", "value": "1.123456"}],
           [{"id": "synthetic", "value": "1.123457"}], numeric_precision={"value": 6})
_v2_expect("Large decimal is not rounded by Python context", "INCORRECT",
           [{"id": "synthetic", "value": "12345678901234567890123456789012345678"}],
           [{"id": "synthetic", "value": "12345678901234567890123456789012345679"}])
_v2_expect("NULL remains different from zero", "INCORRECT",
           [{"id": "synthetic", "value": None}], [{"id": "synthetic", "value": 0}])
_v2_expect("Matching NULL values", "CORRECT",
           [{"id": "synthetic", "value": None}], [{"id": "synthetic", "value": None}])
_v2_expect("Signed zero", "CORRECT",
           [{"id": "synthetic", "value": "-0.00"}], [{"id": "synthetic", "value": 0}])

_v2_two_rows = [{"id": "first", "value": 1}, {"id": "second", "value": 2}]
# Rows: ordering and duplicate counts are separate requirements.
_v2_expect("Required order", "INCORRECT", _v2_two_rows, list(reversed(_v2_two_rows)))
_v2_expect("Unordered multiset", "CORRECT", _v2_two_rows, list(reversed(_v2_two_rows)), ordered=False)
_v2_expect("Expected repeated rows are legitimate", "CORRECT", _v2_base * 2, _v2_base * 2)
_v2_expect("Extra repeated row is not legitimate", "INCORRECT", _v2_base, _v2_base * 2)
_v2_expect("Multiset preserves duplicate counts", "INCORRECT",
           [_v2_two_rows[0], _v2_two_rows[0], _v2_two_rows[1]],
           [_v2_two_rows[0], _v2_two_rows[1], _v2_two_rows[1]], ordered=False)

# Columns: verified aliases can match values without matching the output contract.
_v2_alias_result = _v2_expect("Verified alias", "CORRECT", _v2_base,
                            [{"id": "synthetic", "amount": 12}], aliases={"value": "amount"})
assert _v2_alias_result["contract_compliant"] is False
_v2_extra_result = _v2_expect("Extra metadata does not change business correctness", "CORRECT", _v2_base,
                            [{"id": "synthetic", "value": 12, "metadata": "extra"}])
assert _v2_extra_result["contract_compliant"] is False
_v2_exact_result = _v2_expect("Exact contract", "CORRECT", _v2_base, _v2_base)
assert _v2_exact_result["contract_compliant"] is True
assert _v2_exact_result["expected_hash"] == _v2_exact_result["actual_hash"]
_v2_expect("Unmapped alias is not inferred", "INCORRECT", _v2_base,
           [{"id": "synthetic", "amount": 12}])
_v2_expect("Ambiguous alias mapping", "NOT_EVALUABLE", _v2_base, _v2_base,
           aliases={"id": "value"})
_v2_expect("Duplicate requested column", "NOT_EVALUABLE", _v2_base, _v2_base,
           columns=["id", "value", "value"])
_v2_expect("Missing ground-truth projection", "NOT_EVALUABLE",
           [{"id": "synthetic"}], _v2_base)
_v2_expect("Missing answer projection", "INCORRECT", _v2_base, [{"id": "synthetic"}])

# Invalid values remain errors; date and timestamp types are not guessed.
for _v2_bad_numeric in (True, "NaN", float("nan"), "Infinity", float("inf"), "1,000", "12%", " 12 "):
    _v2_expect("Reject invalid numeric answer", "INCORRECT", _v2_base,
               [{"id": "synthetic", "value": _v2_bad_numeric}])
_v2_expect("Reject invalid reference number", "NOT_EVALUABLE",
           [{"id": "synthetic", "value": float("nan")}], _v2_base)
_v2_expect("No hidden string-to-date coercion", "INCORRECT",
           [{"id": "synthetic", "value": date(2026, 1, 1)}],
           [{"id": "synthetic", "value": "2026-01-01"}], numeric_precision={})
_v2_expect("Aware timestamps use declared UTC rule", "CORRECT",
           [{"id": "synthetic", "value": datetime.fromisoformat("2026-01-01T08:00:00+08:00")}],
           [{"id": "synthetic", "value": datetime.fromisoformat("2026-01-01T00:00:00+00:00")}],
           numeric_precision={})
_v2_expect("Naive timestamp is not silently assigned UTC", "INCORRECT",
           [{"id": "synthetic", "value": datetime(2026, 1, 1)}],
           [{"id": "synthetic", "value": datetime(2026, 1, 1, tzinfo=timezone.utc)}],
           numeric_precision={})
_v2_empty_result = _v2_expect("Two empty result lists", "CORRECT", [], [])
assert _v2_empty_result["contract_compliant"] is None
_v2_expect("Unexpected nonempty answer", "INCORRECT", [], _v2_base)
_v2_expect("Missing actual evidence is not an empty answer", "NOT_EVALUABLE", [], None)
_v2_expect("Answer prose is not structured evidence", "NOT_EVALUABLE", _v2_base, ["No results"])
_v2_expect("Invalid precision", "NOT_EVALUABLE", _v2_base, _v2_base, numeric_precision={"value": True})

V2_SCORING_SELF_TESTS_PASSED = True
print(f"Scorer checks passed: {_v2_test_count} (synthetic data only).")
print("Next: manually run cell 12 once to ask the first question through both agents.")
