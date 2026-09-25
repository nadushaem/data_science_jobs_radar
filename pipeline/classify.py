from pipeline.parsing import (
    find_excluded_roles,
    find_keywords,
    find_roles,
    get_search_text,
)


# текст, по которому ищем ключевые слова конкретной сферы.
# isinstance вместо `or ""` — в company/title может лежать pd.NA/nan
def _industry_text(vacancy, search_text, excludes):
    if not excludes:
        return search_text

    head = " ".join(
        value for value in (vacancy.get("company"), vacancy.get("title")) if isinstance(value, str)
    ).lower()
    if any(phrase in head for phrase in excludes):
        return ""

    text = search_text.lower()
    for phrase in excludes:
        text = text.replace(phrase, " ")
    return text


def classify_vacancy(
    vacancy, target_keywords, role_taxonomy, excluded_roles, industry_excludes=None
):
    search_text = get_search_text(vacancy)
    industry_excludes = industry_excludes or {}

    for category, keywords in target_keywords.items():
        text = _industry_text(vacancy, search_text, industry_excludes.get(category))
        vacancy[category] = find_keywords(text, keywords)

    vacancy["matched_roles"] = find_roles(vacancy.get("title"), role_taxonomy)
    vacancy["excluded_roles"] = find_excluded_roles(vacancy.get("title"), excluded_roles)

    # вакансия попадает в сводку, если: нашли целевую роль,
    # роль не исключена, и сработала хотя бы одна из target_keywords
    vacancy["is_target"] = (
        bool(vacancy["matched_roles"])
        and not vacancy["excluded_roles"]
        and any(vacancy.get(category) for category in target_keywords)
    )

    return vacancy


def classify_vacancies(
    vacancies, target_keywords, role_taxonomy, excluded_roles, industry_excludes=None
):
    return [
        classify_vacancy(vacancy, target_keywords, role_taxonomy, excluded_roles, industry_excludes)
        for vacancy in vacancies
    ]
