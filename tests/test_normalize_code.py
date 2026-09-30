import pytest
from base_schemas.ingestion.normalization import normalize_code


@pytest.mark.parametrize("value", ["P012", " sub-01 ", "mouse_042", "run.3", "A"])
def test_normalize_code_accepts_codes(value):
    assert normalize_code(value, field="subject_code", max_length=64) == value.strip()


@pytest.mark.parametrize(
    "value, match",
    [
        ("", "non-empty"),
        ("   ", "non-empty"),
        ("Jan de Vries", "pseudonymous code"),
        ("Doe, John", "pseudonymous code"),
        ("José", "pseudonymous code"),
        ("-leading-dash", "pseudonymous code"),
        ("x" * 65, "longer than 64"),
    ],
)
def test_normalize_code_rejects(value, match):
    with pytest.raises(ValueError, match=match):
        normalize_code(value, field="subject_code", max_length=64)
