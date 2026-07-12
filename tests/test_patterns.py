from sidecar.perception.patterns import _probe_pattern


class ValuePattern:
    Value = "client-secret-123"
    ReadOnly = False


def test_value_patterns_are_redacted_by_default():
    result = _probe_pattern("value", ValuePattern())

    assert result["value"] == "[REDACTED]"
    assert result["value_length"] == 17


def test_raw_values_require_explicit_opt_in():
    result = _probe_pattern("value", ValuePattern(), include_raw_values=True)

    assert result["value"] == "client-secret-123"
