import re
import pandas as pd


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


# получаем нормализованный датафрейм
# ВАЖНО: salary_min/salary_max/currency/salary_period/published_at
# на этом этапе уже готовы — их парсит сам источник (см. sources/*.py),
# здесь только приводим типы и общие текстовые поля
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
        df["location"] = df["location"].map(normalize_location)

    if "work_format" in df.columns:
        df["work_format"] = df["work_format"].map(normalize_work_format)

    if "salary_min" in df.columns:
        df["salary_min"] = pd.to_numeric(df["salary_min"], errors="coerce")

    if "salary_max" in df.columns:
        df["salary_max"] = pd.to_numeric(df["salary_max"], errors="coerce")

    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    return df