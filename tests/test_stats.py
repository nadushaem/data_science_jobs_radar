import pandas as pd
import pytest
import requests

from pipeline import stats
from storage.vacancies import archive_targets

CBR_PAYLOAD = {
    "Valute": {
        "USD": {"Value": 90.0, "Nominal": 1},
        "EUR": {"Value": 1000.0, "Nominal": 10},  # номинал ≠ 1, проверяем деление
    },
}


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return CBR_PAYLOAD


def test_to_rub():
    rates = {"RUB": 1.0, "USD": 90.0}
    assert stats.to_rub(1000, "USD", rates) == 90_000
    assert stats.to_rub(1000, None, rates) == 1000
    assert stats.to_rub(None, "USD", rates) is None


@pytest.mark.parametrize(
    ("period", "salary", "expected"),
    [("month", 100_000, 100_000), ("year", 1_200_000, 100_000), ("hour", 1000, 168_000)],
)
def test_normalize_salary_period(period, salary, expected):
    row = {"salary_period": period, "salary_min": salary, "salary_max": None}
    assert stats._normalize_salary_period(row) == (expected, None)


def test_exchange_rates_from_cbr(monkeypatch):
    monkeypatch.setattr(stats.requests, "get", lambda *args, **kwargs: _FakeResponse())
    rates = stats.get_exchange_rates()

    # gbp в ответе нет — должен подставиться фолбэк
    assert rates == {"RUB": 1.0, "USD": 90.0, "EUR": 100.0, "GBP": stats.FALLBACK_RATES["GBP"]}


def test_exchange_rates_fallback(monkeypatch):
    def _fail(*args, **kwargs):
        raise requests.ConnectionError("нет сети")

    monkeypatch.setattr(stats.requests, "get", _fail)
    assert stats.get_exchange_rates() == {"RUB": 1.0, **stats.FALLBACK_RATES}


def test_add_rub_salaries():
    df = pd.DataFrame([{"salary_min": 1000, "salary_max": None, "currency": "USD"}])
    result = stats.add_rub_salaries(df, {"RUB": 1.0, "USD": 90.0})

    assert result["salary_min_rub"].iloc[0] == 90_000
    assert pd.isna(result["salary_max_rub"].iloc[0])


def test_top_skills_reads_archive():
    archive_targets(
        pd.DataFrame([
            {"url": "a", "skills": ["python", "sql"], "matched_roles": ["data_scientist"],
             "fintech": ["банк"]},
            {"url": "b", "skills": ["python"], "matched_roles": ["ml_engineer"], "it": ["it"]},
        ])
    )  # fmt: skip

    assert stats.top_skills() == [("python", 2), ("sql", 1)]
    assert stats.top_skills(industries=["fintech"]) == [("python", 1), ("sql", 1)]
    assert stats.top_skills(roles=["ml_engineer"]) == [("python", 1)]
