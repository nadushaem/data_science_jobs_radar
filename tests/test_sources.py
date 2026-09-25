import pandas as pd
import pytest

from sources import geekjob, getmatch, hirify


def test_geekjob_date_rolls_over_year(freeze_now):
    freeze_now(geekjob)  # «сейчас» — 5 января 2026

    assert geekjob.parse_geekjob_date("3 января") == pd.Timestamp("2026-01-03")
    assert geekjob.parse_geekjob_date("30 декабря") == pd.Timestamp("2025-12-30")
    assert pd.isna(geekjob.parse_geekjob_date("неизвестно"))


@pytest.mark.parametrize(
    ("text", "delta"),
    [
        ("5 минут назад", pd.Timedelta(minutes=5)),
        ("2 часа назад", pd.Timedelta(hours=2)),
        ("3 дня назад", pd.Timedelta(days=3)),
        ("1 неделю назад", pd.Timedelta(weeks=1)),
        ("вчера", pd.Timedelta(days=1)),
    ],
)
def test_hirify_relative_date(freeze_now, text, delta):
    now = freeze_now(hirify)
    assert hirify.parse_relative_date(text) == pd.Timestamp(now) - delta


def test_hirify_unknown_date():
    assert pd.isna(hirify.parse_relative_date("давно"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("от 600 000 ₽/мес на руки", (600_000, None, "RUB")),
        ("6 000 — 7 000 €/мес на руки", (6000, 7000, "EUR")),
        ("до 5 000 $/мес", (None, 5000, "USD")),
        (None, (None, None, None)),
    ],
)
def test_getmatch_salary_description(text, expected):
    assert getmatch._parse_salary_description(text) == expected


def test_getmatch_parse_offer_uses_salary_fallback():
    offer = {
        "position": "Senior Data Scientist",
        "company": {"name": "Acme"},
        "location_items": [{"label": "Москва", "format": "remote"}],
        "salary_description": "от 300 000 ₽/мес на руки",
        "url": "/vacancies/1",
        "offer_description": "<p>Финтех</p>",
        "skills_objects": [{"name": "Python"}],
    }
    result = getmatch._parse_offer(offer)

    assert result["url"] == "https://getmatch.ru/vacancies/1"
    assert (result["salary_min"], result["currency"]) == (300_000, "RUB")
    assert result["skills"] == ["python"]
    assert result["description"] == "Финтех"
    assert result["level"] == ["Сеньор"]
