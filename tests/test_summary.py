import pandas as pd
import pytest

from pipeline.summary import build_summary_messages, filter_vacancies


def _row(url, fintech=False, edtech=False, roles=("data_scientist",), is_target=True):
    return {
        "url": url,
        "title": f"вакансия {url}",
        "is_target": is_target,
        "fintech": ["финтех"] if fintech else [],
        "edtech": ["edtech"] if edtech else [],
        "matched_roles": list(roles),
    }


@pytest.fixture
def df():
    rows = [
        _row("1", fintech=True),
        _row("2", edtech=True),
        _row("3", fintech=True, roles=["data_analyst"]),
        _row("4", fintech=True, is_target=False),
    ]
    return pd.DataFrame(rows)


def test_filter_without_filters_returns_all_target(df):
    assert list(filter_vacancies(df)["url"]) == ["1", "2", "3"]


def test_filter_by_industry_and_role(df):
    result = filter_vacancies(df, industries=["fintech"], roles=["data_scientist"])
    assert list(result["url"]) == ["1"]


def test_filter_by_several_industries(df):
    result = filter_vacancies(df, industries=["fintech", "edtech"])
    assert list(result["url"]) == ["1", "2", "3"]


def test_summary_is_split_by_max_length():
    df = pd.DataFrame([_row(f"https://x/{i}") for i in range(30)])
    messages = build_summary_messages(df, is_new_subscriber=True, max_length=300)

    assert len(messages) > 1
    assert all(len(message) <= 300 for message in messages)
    assert messages[0].startswith("📅")
