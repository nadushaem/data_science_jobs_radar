import os
import pandas as pd
import requests

from keywords import TARGET_KEYWORDS

STATS_FILE = "data/vacancies_stats.pkl"

# сколько рабочих часов в месяце берём для конвертации почасовой ставки
HOURS_PER_MONTH = 168

STATS_COLUMNS = [
    "title", "company", "location", "work_format", "source",
    "published_at", "specialization", "level", "skills",
    "salary_min", "salary_max",
    *TARGET_KEYWORDS.keys(),
    "matched_roles",
    "url",  # служебное поле — нужно для дедупликации архива между прогонами
]

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

# запасные курсы на случай, если цб недоступен
# нужно периодически поправлять руками
FALLBACK_RATES = {
    "USD": 95.0,
    "EUR": 105.0,
    "GBP": 120.0,
}


# тянем актуальные курсы валют к рублю с цб рф, при ошибке — фолбэк
def get_exchange_rates():
    try:
        response = requests.get(CBR_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        rates = {"RUB": 1.0}
        for code in FALLBACK_RATES:
            valute = data.get("Valute", {}).get(code)
            if valute:
                # value уже за nominal единиц валюты
                rates[code] = valute["Value"] / valute["Nominal"]
            else:
                rates[code] = FALLBACK_RATES[code]

        return rates

    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"не удалось получить курсы цб, использую фолбэк: {error}")
        return {"RUB": 1.0, **FALLBACK_RATES}


# конвертируем сумму в рубли по словарю курсов
def to_rub(amount, currency, rates):
    if amount is None or (isinstance(amount, float) and amount != amount):  # nan
        return amount

    # если валюта не распознана — считаем, что это уже рубли
    rate = rates.get(currency, 1.0) if currency else 1.0
    return round(amount * rate)


# приводим зарплату к месяцу: год делим на 12, час умножаем на норму часов
def _normalize_salary_period(row):
    period = row.get("salary_period")
    salary_min, salary_max = row.get("salary_min"), row.get("salary_max")

    if period == "year":
        factor = 1 / 12
    elif period == "hour":
        factor = HOURS_PER_MONTH
    else:
        # month или неизвестно — считаем, что уже месяц
        factor = 1

    to_month = lambda value: round(value * factor) if pd.notna(value) else value
    return to_month(salary_min), to_month(salary_max)


# строим финальный датасет для статистики из классифицированных вакансий
def build_stats_dataset(df, exchange_rates=None):
    if exchange_rates is None:
        exchange_rates = {"RUB": 1.0}

    df = df[df["is_target"]].copy()

    # зарплата → месяц, затем → рубли
    normalized = df.apply(_normalize_salary_period, axis=1, result_type="expand")
    df["salary_min"], df["salary_max"] = normalized[0], normalized[1]

    df["salary_min"] = df.apply(
        lambda row: to_rub(row["salary_min"], row.get("currency"), exchange_rates), axis=1
    )
    df["salary_max"] = df.apply(
        lambda row: to_rub(row["salary_max"], row.get("currency"), exchange_rates), axis=1
    )

    # категории сфер — списки найденных ключевых слов превращаем в bool
    for category in TARGET_KEYWORDS:
        if category in df.columns:
            df[category] = df[category].map(bool)
        else:
            df[category] = False

    return df.reindex(columns=STATS_COLUMNS)


# читаем существующий архив статистики, если он есть
def load_stats():
    if not os.path.exists(STATS_FILE):
        empty = pd.DataFrame(columns=STATS_COLUMNS)
        for category in TARGET_KEYWORDS:
            empty[category] = empty[category].astype(bool)
        return empty

    return pd.read_pickle(STATS_FILE)


# дописываем новые вакансии в архив статистики, убирая дубли по url
def append_stats(new_stats_df):
    archive = load_stats()

    combined = pd.concat([archive, new_stats_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["url"], keep="last")
    bool_columns = list(TARGET_KEYWORDS)
    combined[bool_columns] = combined[bool_columns].fillna(False).astype(bool)

    combined["published_at"] = pd.to_datetime(combined["published_at"], errors="coerce")
    combined["salary_min"] = pd.to_numeric(combined["salary_min"], errors="coerce")
    combined["salary_max"] = pd.to_numeric(combined["salary_max"], errors="coerce")

    combined = combined.sort_values("published_at").reset_index(drop=True)

    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    combined.to_pickle(STATS_FILE)

    return combined