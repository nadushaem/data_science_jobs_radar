from collections import Counter

import pandas as pd
import requests

from storage.vacancies import load_target_vacancies

# сколько рабочих часов в месяце берем для конвертации почасовой ставки
HOURS_PER_MONTH = 168

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

# запасные курсы на случай, если цб недоступен
# нужно периодически поправлять руками
FALLBACK_RATES = {
    "USD": 85.0,
    "EUR": 95.0,
    "GBP": 115.0,
}


# тянем актуальные курсы валют к рублю с цб рф, при ошибке — фолбэк
def get_exchange_rates():
    try:
        response = requests.get(CBR_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        rates = {"RUB": 1.0}
        for code, fallback_rate in FALLBACK_RATES.items():
            valute = data.get("Valute", {}).get(code)
            if valute:
                rates[code] = valute["Value"] / valute["Nominal"]
            else:
                rates[code] = fallback_rate

    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"не удалось получить курсы цб, использую фолбэк: {error}")
        return {"RUB": 1.0, **FALLBACK_RATES}
    return rates


# конвертируем сумму в рубли по словарю курсов
def to_rub(amount, currency, rates):
    if amount is None or pd.isna(amount):
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

    def to_month(value):
        return round(value * factor) if pd.notna(value) else value

    return to_month(salary_min), to_month(salary_max)


# зарплата в рублях за месяц — её храним в target_vacancies для статистики
def add_rub_salaries(df, exchange_rates):
    def convert(row):
        currency = row.get("currency")
        return [to_rub(value, currency, exchange_rates) for value in _normalize_salary_period(row)]

    salaries = [convert(row) for row in df.to_dict("records")]
    return df.assign(
        salary_min_rub=[low for low, _ in salaries], salary_max_rub=[high for _, high in salaries]
    )


# вакансия попадает в подсчёт, если хотя бы одна из выбранных сфер = True.
# если сферы не выбраны — берём все вакансии (аналогично summary.py)
def _industry_mask(df, industries):
    columns = [key for key in industries if key in df.columns]
    if not columns:
        return pd.Series(True, index=df.index)
    return df[columns].any(axis=1)


# вакансия попадает в подсчёт, если matched_roles пересекается с выбранными ролями
def _role_mask(df, roles):
    if not roles or "matched_roles" not in df.columns:
        return pd.Series(True, index=df.index)
    wanted = set(roles)
    return df["matched_roles"].map(lambda matched: bool(wanted.intersection(matched or [])))


# считаем топ-N навыков по архиву статистики с учётом фильтров подписчика
def top_skills(industries=None, roles=None, top_n=5):
    df = load_target_vacancies()  # весь архив целевых вакансий
    if df.empty:
        return []

    mask = _industry_mask(df, industries or []) & _role_mask(df, roles or [])
    filtered = df[mask]

    counter = Counter()
    for skills in filtered["skills"].dropna():
        if isinstance(skills, list):
            counter.update(skills)

    return counter.most_common(top_n)


# собираем текст сообщения для бота — отдельно от подсчёта,
# чтобы top_skills можно было переиспользовать и без телеграма
def build_top_skills_message(industries=None, roles=None, top_n=5):
    ranked = top_skills(industries, roles, top_n)

    if not ranked:
        return "Пока не набралось данных для статистики по этому фильтру 🤷"

    lines = [f"🏆 *Топ-{len(ranked)} навыков в вакансиях*"]
    for i, (skill, count) in enumerate(ranked, 1):
        lines.append(f"{i}. {skill}: {count}")

    return "\n".join(lines)
