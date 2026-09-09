# Notebook cell 10 (file 35) | Compare recorded answers with the reference rows
# Loads comparison functions only. Next, run the synthetic checks in cell 11.
# Supply an alias only after verifying that both column names mean the same thing.

# Timestamps with a timezone are compared in UTC; those without one stay unchanged.
# Date strings stay strings. This rule does not infer source timezones.
V2_SCORING_DATETIME_RULE = "aware_utc_naive_unchanged"
V2_SCORING_SELF_TESTS_PASSED = False


def _v2_decimal(value):
    """Read a plain finite number without silently cleaning or changing it."""
    if isinstance(value, bool):
        raise ValueError("A Boolean is not a numeric measure.")
    if not isinstance(value, (int, float, Decimal, str)):
        raise ValueError("Unsupported numeric representation.")
    text = str(value)
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
        raise ValueError("Expected a plain number, without commas, percent signs or spaces.")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("The numeric value could not be read.") from exc
    if not number.is_finite():
        raise ValueError("NaN and infinity are not valid comparison values.")
    digits = number.as_tuple()
    if len(digits.digits) > 1000 or abs(digits.exponent) > 1000:
        raise ValueError("The numeric value is outside the scorer's supported size.")
    return number


def _v2_decimal_token(number, precision):
    """Create an exact token; fixed precision uses decimal half-up rounding."""
    parts = number.as_tuple()
    coefficient = int("".join(str(digit) for digit in parts.digits))
    exponent = parts.exponent
    if precision is not None:
        shift = exponent + precision
        if shift >= 0:
            coefficient *= 10 ** shift
        else:
            divisor = 10 ** (-shift)
            coefficient, remainder = divmod(coefficient, divisor)
            if remainder * 2 >= divisor:
                coefficient += 1
        exponent = -precision
    if coefficient == 0:
        return "0"
    while coefficient % 10 == 0:
        coefficient //= 10
        exponent += 1
    sign = "-" if parts.sign else ""
    return f"{sign}{coefficient}e{exponent}"


def _v2_value_token(value, is_numeric, precision):
    if value is None:
        return ["null"]
    if is_numeric:
        return ["number", _v2_decimal_token(_v2_decimal(value), precision)]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, datetime):
        if V2_SCORING_DATETIME_RULE != "aware_utc_naive_unchanged":
            raise ValueError("The datetime serialization rule is not recognized.")
        if value.utcoffset() is not None:
            return ["datetime_utc", value.astimezone(timezone.utc).isoformat()]
        return ["datetime_naive", value.isoformat()]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    if isinstance(value, str):
        return ["text", value]
    if isinstance(value, (int, float, Decimal)):
        return ["number", _v2_decimal_token(_v2_decimal(value), None)]
    raise ValueError("An output value has an unsupported type.")


def _v2_row_tokens(rows, columns, numeric_precision, names):
    tokens = []
    for row_number, row in enumerate(rows, 1):
        values = []
        for column in columns:
            try:
                values.append(_v2_value_token(
                    row[names[column]], column in numeric_precision,
                    numeric_precision.get(column),
                ))
            except (ValueError, TypeError, OverflowError) as exc:
                # Do not include customer values in diagnostics.
                raise ValueError(
                    f"Row {row_number}, column {column}: {exc}"
                ) from exc
        tokens.append(json.dumps(values, ensure_ascii=False, separators=(",", ":")))
    return tokens


def _v2_tokens_hash(tokens, ordered):
    canonical = tokens if ordered else sorted(tokens)
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def score_section(expected_rows, actual_rows, columns, numeric_precision, aliases, ordered=True):
    """Compare structured rows, not prose, with the selected reference columns.

    numeric_precision maps numeric columns to decimal places, or None for exact
    values. Unlisted columns retain their types. aliases maps canonical names to
    actual response names. Supplying an alias confirms its meaning was checked.

    Correct business values can pass even when naming or extra columns violate
    the output contract. An empty answer requires separate retrieval evidence;
    this function cannot prove that an empty list came from a real query.
    """
    result = {
        "status": "NOT_EVALUABLE",
        "reasons": [],
        "hashes": {"expected": None, "actual": None},
        "expected_hash": None,
        "actual_hash": None,
        "contract_compliant": None,
        "contract_reasons": [],
        "expected_row_count": len(expected_rows) if isinstance(expected_rows, list) else None,
        "actual_row_count": len(actual_rows) if isinstance(actual_rows, list) else None,
    }

    def stop(status, reason):
        result["status"] = status
        result["reasons"].append(reason)
        return result

    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
        return stop("NOT_EVALUABLE", "Both evidence inputs must be lists of structured rows.")
    if not isinstance(columns, list) or not columns or any(
        not isinstance(column, str) or not column for column in columns
    ) or len(set(columns)) != len(columns):
        return stop("NOT_EVALUABLE", "The reference projection must contain unique column names.")
    if not isinstance(numeric_precision, dict) or not isinstance(aliases, dict):
        return stop("NOT_EVALUABLE", "Precision and verified alias rules must be dictionaries.")
    if not isinstance(ordered, bool):
        return stop("NOT_EVALUABLE", "The ordering rule must be explicitly True or False.")
    if any(column not in columns for column in numeric_precision):
        return stop("NOT_EVALUABLE", "A precision rule names a column outside the projection.")
    if any(
        precision is not None and (
            isinstance(precision, bool) or not isinstance(precision, int)
            or not 0 <= precision <= 38
        )
        for precision in numeric_precision.values()
    ):
        return stop("NOT_EVALUABLE", "Numeric precision must be None or an integer from 0 to 38.")
    if any(
        column not in columns or not isinstance(name, str) or not name
        for column, name in aliases.items()
    ):
        return stop("NOT_EVALUABLE", "An alias rule is invalid or outside the projection.")
    actual_names = {column: aliases.get(column, column) for column in columns}
    if len(set(actual_names.values())) != len(actual_names):
        return stop("NOT_EVALUABLE", "Two reference columns map to the same answer column.")
    if any(not isinstance(row, dict) for row in expected_rows):
        return stop("NOT_EVALUABLE", "A reference row is not a dictionary.")
    if any(not isinstance(row, dict) for row in actual_rows):
        return stop("NOT_EVALUABLE", "An answer row is not a dictionary. Check the values copied from the saved response.")
    if any(any(column not in row for column in columns) for row in expected_rows):
        return stop("NOT_EVALUABLE", "The reference evidence is missing a required column.")

    expected_names = {column: column for column in columns}
    try:
        expected_tokens = _v2_row_tokens(expected_rows, columns, numeric_precision, expected_names)
    except ValueError as exc:
        return stop("NOT_EVALUABLE", f"Invalid reference evidence. {exc}")
    result["expected_hash"] = _v2_tokens_hash(expected_tokens, ordered)
    result["hashes"]["expected"] = result["expected_hash"]

    if actual_rows:
        expected_column_set = set(columns)
        result["contract_compliant"] = all(
            set(row) == expected_column_set for row in actual_rows
        ) and all(actual_names[column] == column for column in columns)
        if not result["contract_compliant"]:
            result["contract_reasons"].append(
                "Answer names or extra/missing columns differ from the requested projection."
            )
    else:
        result["contract_reasons"].append("An empty row list does not provide column-schema evidence.")
    if any(any(name not in row for name in actual_names.values()) for row in actual_rows):
        return stop("INCORRECT", "The recorded answer is missing a required business column.")
    try:
        actual_tokens = _v2_row_tokens(actual_rows, columns, numeric_precision, actual_names)
    except ValueError as exc:
        return stop("INCORRECT", f"Invalid answer value. {exc}")
    result["actual_hash"] = _v2_tokens_hash(actual_tokens, ordered)
    result["hashes"]["actual"] = result["actual_hash"]

    if len(expected_tokens) != len(actual_tokens):
        return stop("INCORRECT", "The answer row count differs from the reference.")
    matches = expected_tokens == actual_tokens if ordered else Counter(expected_tokens) == Counter(actual_tokens)
    if not matches:
        if ordered and Counter(expected_tokens) == Counter(actual_tokens):
            return stop("INCORRECT", "The values match, but the requested row order does not.")
        return stop("INCORRECT", "The requested business values or row membership differ.")
    return stop("CORRECT", "The requested rows and values match the reference under the declared rules.")


print("Scoring helpers loaded. Run cell 11 to test them with synthetic data.")
