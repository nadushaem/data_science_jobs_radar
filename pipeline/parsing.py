import re

from bs4 import BeautifulSoup


# поиск ключевых слов
def find_keywords(text, keywords):
    if not text:
        return []

    text = text.lower()
    found = []
    for keyword in keywords:
        if keyword.lower() in text:
            found.append(keyword)
    return found


# схлопываем пробелы вокруг / и - , чтобы "ai / ml" == "ai/ml"
def _normalize_for_matching(text):
    text = text.lower()
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


# поиск целевых ролей по таксономии, возвращает canonical roles
def find_roles(title, role_taxonomy):
    if not title:
        return []

    title = _normalize_for_matching(title)

    found = []
    for canonical_role, aliases in role_taxonomy.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(_normalize_for_matching(alias)) + r"\b"

            if re.search(pattern, title):
                found.append(canonical_role)
                break  # одна роль — не дублируем по разным алиасам

    return found


# исключаем неинтересные должности
def find_excluded_roles(title, excluded_roles):
    if not title:
        return []

    title = title.lower()

    return [
        role
        for role in excluded_roles
        if role.lower() in title
    ]


# убираем html-теги из текста (например, offer_description с getmatch)
def strip_html(value):
    if not value:
        return None

    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


# собираем текст по всей вакансии
def get_search_text(vacancy):
    parts = [
        vacancy.get("title"),
        vacancy.get("description"),
        vacancy.get("specialization"),
        vacancy.get("industry"),
        vacancy.get("skills"),
    ]

    text_parts = []

    for part in parts:
        if isinstance(part, list):
            text_parts.extend(part)

        elif part:
            text_parts.append(str(part))

    return " ".join(text_parts)


# грубая оценка грейда по названию вакансии (для источников без готового тега)
def guess_level(title, level_taxonomy):
    if not title:
        return None

    normalized = _normalize_for_matching(title)
    found = []

    for grade, aliases in level_taxonomy.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(_normalize_for_matching(alias)) + r"\b"

            if not re.search(pattern, normalized):
                continue

            # "lead" — самый шумный алиас: ловит "Lead Generation Manager",
            # который к грейду вообще не относится
            if alias == "lead" and "generation" in normalized:
                continue

            found.append(grade)
            break

    return found or None


def parse_salary(value, detect_period=True):
    result = {
        "salary_min": None,
        "salary_max": None,
        "currency": None,
        "salary_period": "month",
    }

    if not value:
        return result

    raw = str(value).lower().replace("\xa0", " ")
    raw = re.sub(r"(?<=\d),(?=\d{3}(\D|$))", "", raw)
    raw = raw.replace(",", ".")

    if any(x in raw for x in ["₽", "руб", "rub"]):
        result["currency"] = "RUB"
    elif any(x in raw for x in ["$", "usd"]):
        result["currency"] = "USD"
    elif any(x in raw for x in ["€", "eur"]):
        result["currency"] = "EUR"
    elif any(x in raw for x in ["£", "gbp"]):
        result["currency"] = "GBP"

    if detect_period:
        if any(x in raw for x in ["год", "year", "/year", "per year"]):
            result["salary_period"] = "year"
        elif any(x in raw for x in ["час", "hour", "/hour", "per hour"]):
            result["salary_period"] = "hour"

    numbers = re.findall(
        r"\d[\d\s]*(?:\.\d+)?\s*(?:k|к|тыс\.?)?",
        raw,
    )

    values = []
    for item in numbers:
        item = item.replace(" ", "")
        if not item:
            continue

        if re.search(r"(k|к|тыс)", item):
            number = float(re.sub(r"(k|к|тыс\.?)", "", item))
            number *= 1000
        else:
            number = float(item)

        values.append(int(number) if number.is_integer() else number)

    values = [value for value in values if value < 10_000_000]
    if not values:
        return result

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