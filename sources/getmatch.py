import re
from urllib.parse import urljoin
from datetime import datetime, timedelta

import pandas as pd
import requests

from functions import strip_html, guess_level
from keywords import LEVEL_TAXONOMY


SOURCE_NAME = "getmatch"
BASE_URL = "https://getmatch.ru"
API_URL = "https://getmatch.ru/api/offers"


# резервный парсинг зарплаты из salary_description — нужен, когда
# salary_hidden=true и salary_display_from/to пустые, но текст с суммой есть
# (например: "от 600 000 ₽/мес на руки", "6 000 — 7 000 €/мес на руки")
def _parse_salary_description(text):
    if not text:
        return None, None, None

    raw = text.replace("\xa0", " ").replace("\u200d", "")

    currency = None
    if "₽" in raw:
        currency = "RUB"
    elif "$" in raw:
        currency = "USD"
    elif "€" in raw:
        currency = "EUR"
    elif "£" in raw:
        currency = "GBP"

    numbers = [
        int(n.replace(" ", ""))
        for n in re.findall(r"\d[\d ]*\d|\d", raw)
    ]
    numbers = [n for n in numbers if n < 10_000_000]

    if not numbers:
        return None, None, currency

    raw_lower = raw.lower()
    if "от " in raw_lower:
        return numbers[0], None, currency
    if "до " in raw_lower:
        return None, numbers[0], currency
    if len(numbers) >= 2:
        return min(numbers[:2]), max(numbers[:2]), currency

    return numbers[0], None, currency


def _parse_offer(offer):
    location_items = offer.get("location_items") or []
    primary_location = location_items[0] if location_items else {}

    skills = [
        skill["name"].lower()
        for skill in offer.get("skills_objects") or []
        if skill.get("name")
    ]

    salary_min = offer.get("salary_display_from")
    salary_max = offer.get("salary_display_to")
    currency = offer.get("salary_currency")

    if salary_min is None and salary_max is None:
        salary_min, salary_max, fallback_currency = _parse_salary_description(
            offer.get("salary_description")
        )
        currency = currency or fallback_currency

    return {
        "title": offer.get("position"),
        "company": (offer.get("company") or {}).get("name"),
        "location": primary_location.get("label"),
        "work_format": primary_location.get("format"),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "salary_period": "month",  # у getmatch зарплата всегда указана в месяц
        "published_at": pd.to_datetime(offer.get("published_at"), errors="coerce"),
        "url": urljoin(BASE_URL, offer.get("url") or ""),
        "description": strip_html(offer.get("offer_description")),
        "skills": skills,
        "source": SOURCE_NAME,
        "level": guess_level(offer.get("position"), LEVEL_TAXONOMY),
    }


# получаем вакансии с getmatch через их внутренний api за последние N дней
def fetch_vacancies(days=7, limit=20):
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=days))
    vacancies = []
    offset = 0

    while True:
        response = requests.get(
            API_URL,
            params={
                "sa": "any",
                "p": offset // limit + 1,
                "offset": offset,
                "limit": limit,
                "pa": "all",
            },
        )
        response.raise_for_status()
        data = response.json()

        offers = data.get("offers") or []
        if not offers:
            break

        stop = False

        for offer in offers:
            if offer.get("offer_type") != "vacancy":
                continue
            if not offer.get("is_active"):
                continue

            published_at = pd.to_datetime(offer.get("published_at"), errors="coerce")
            if pd.isna(published_at) or published_at < cutoff:
                stop = True
                continue

            vacancies.append(_parse_offer(offer))

        offset += limit
        total = (data.get("meta") or {}).get("total", 0)
        if stop or offset >= total:
            break

    return vacancies