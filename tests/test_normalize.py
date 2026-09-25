import pandas as pd
import pytest

from pipeline import normalize


def test_normalize_text():
    assert normalize.normalize_text("  Data   Scientist ") == "data scientist"
    assert pd.isna(normalize.normalize_text("   "))
    assert pd.isna(normalize.normalize_text(None))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("г. Москва", "москва"),
        ("Город Санкт-Петербург", "санкт-петербург"),
        ("мск", "москва"),
        ("СПб", "санкт-петербург"),
    ],
)
def test_normalize_location(raw, expected):
    assert normalize.normalize_location(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Удалённо", "remote"),
        ("office", "onsite"),
        ("Гибрид", "hybrid"),
        ("Гибрид: офис + удалёнка", "hybrid"),
    ],
)
def test_normalize_work_format(raw, expected):
    assert normalize.normalize_work_format(raw) == expected


def test_normalize_dataframe_types():
    df = pd.DataFrame(
        {"title": [" Data Scientist "], "salary_min": ["100000"], "published_at": ["2026-09-01"]}
    )
    result = normalize.normalize_dataframe(df)

    assert result.loc[0, "title"] == "data scientist"
    assert result.loc[0, "salary_min"] == 100_000
    assert pd.api.types.is_datetime64_any_dtype(result["published_at"])
