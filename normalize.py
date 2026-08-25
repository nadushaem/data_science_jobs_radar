import re
import pandas as pd
from datetime import datetime


# приводим текст к единому виду
def normalize_text(value):
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

    return value.lower() if value else pd.NA


# приводим местоположение к единому виду
def normalize_location(value):
    value = normalize_text(value)

    if pd.isna(value):
        return pd.NA

    value = re.sub(r"^г\.\s*", "", value)
    value = re.sub(r"^город\s+", "", value)
    value = value.strip(" ,")

    aliases = {
        "мск": "москва",
        "spb": "санкт-петербург",
        "с.петербург": "санкт-петербург",
        "петербург": "санкт-петербург",
    }

    return aliases.get(value, value)


# приводим формат работы к единому виду
def normalize_work_format(value):
    value = normalize_text(value)

    if pd.isna(value):
        return pd.NA

    if any(word in value for word in [
        "remote",
        "удален",
        "удалён",
        "дистанцион",
    ]):
        return "remote"

    if any(word in value for word in [
        "office",
        "офис",
    ]):
        return "onsite"

    if any(word in value for word in [
        "hybrid",
        "гибрид",
    ]):
        return "hybrid"

    return value


# парсим зп
def parse_salary(value):
    result = {
        "salary_min": pd.NA,
        "salary_max": pd.NA,
        "currency": pd.NA,
        "salary_period": pd.NA,
    }

    if pd.isna(value):
        return result

    raw = str(value).lower()
    raw = raw.replace("\xa0", " ")
    raw = raw.replace(",", ".")

    # валюта
    if any(x in raw for x in ["₽", "руб", "rub"]):
        result["currency"] = "RUB"
    elif any(x in raw for x in ["$", "usd"]):
        result["currency"] = "USD"
    elif any(x in raw for x in ["€", "eur"]):
        result["currency"] = "EUR"
    elif any(x in raw for x in ["£", "gbp"]):
        result["currency"] = "GBP"

    # период
    if any(x in raw for x in ["год", "year", "/year", "per year"]):
        result["salary_period"] = "year"
    elif any(x in raw for x in ["час", "hour", "/hour", "per hour"]):
        result["salary_period"] = "hour"
    else:
        result["salary_period"] = "month"

    # числа
    numbers = re.findall(
        r"\d+(?:\.\d+)?\s*(?:k|к|тыс\.?)?",
        raw,
    )

    values = []

    for item in numbers:
        item = item.replace(" ", "")

        if re.search(r"(k|к|тыс)", item):
            number = float(
                re.sub(r"(k|к|тыс\.?)", "", item)
            )
            number *= 1000
        else:
            number = float(item)

        values.append(
            int(number) if number.is_integer() else number
        )

    values = [value for value in values if value < 10_000_000]
    if not values:
        return result

    # диапазон зарплаты
    if any(x in raw for x in ["от ", "from ", ">="]):
        result["salary_min"] = values[0]

    elif any(x in raw for x in ["до ", "up to ", "<="]):
        result["salary_max"] = values[0]

    elif len(values) >= 2:
        result["salary_min"] = min(values[:2])
        result["salary_max"] = max(values[:2])

    else:
        result["salary_min"] = values[0]

    return result


# парсим дату
def parse_geekjob_date(value):

    if pd.isna(value): return pd.NaT

    months = {
        "января": 1,
        "февраля": 2,
        "марта": 3,
        "апреля": 4,
        "мая": 5,
        "июня": 6,
        "июля": 7,
        "августа": 8,
        "сентября": 9,
        "октября": 10,
        "ноября": 11,
        "декабря": 12}

    match = re.match(r"(\d{1,2})\s+([а-яё]+)", str(value).lower().strip())

    if not match or match.group(2) not in months: return pd.NaT

    day, month = int(match.group(1)), months[match.group(2)]
    now = datetime.now()
    year = now.year

    date = pd.Timestamp(year=year, month=month, day=day)
    if date > pd.Timestamp(now) + pd.Timedelta(days=1): date = date.replace(year=year - 1)

    return date


# получаем нормализованный датафрейм
def normalize_dataframe(df):
    df = df.copy()

    for column in [
        "title",
        "company",
        "description",
    ]:
        if column in df.columns:
            df[column] = df[column].map(normalize_text)

    if "location" in df.columns:
        df["location"] = (df["location"].map(normalize_location))

    if "work_format" in df.columns:
        df["work_format"] = (df["work_format"].map(normalize_work_format))

    if "salary" in df.columns:
        salary_data = df["salary"].apply(parse_salary).apply(pd.Series)

        df["salary_min"] = pd.to_numeric(salary_data["salary_min"], errors="coerce")
        df["salary_max"] = pd.to_numeric(salary_data["salary_max"], errors="coerce")

        df["currency"] = salary_data["currency"]
        df["salary_period"] = salary_data["salary_period"]

        df = df.drop(columns=["salary"])

    if "date" in df.columns:
        df["published_at"] = df["date"].map(parse_geekjob_date)
    df = df.drop(columns=["date"])

    return df