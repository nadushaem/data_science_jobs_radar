from bs4 import BeautifulSoup
import re
from keywords import LEVEL_KEYWORDS

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


# грубая оценка уровня по названию вакансии (для источников без готового тега)
def guess_level(title):
    if not title:
        return None

    title = title.lower()
    found = [
        level
        for level, keywords in LEVEL_KEYWORDS.items()
        if any(keyword in title for keyword in keywords)
    ]

    return found or None