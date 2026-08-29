from parsing import get_search_text, find_keywords, find_roles, find_excluded_roles


def classify_vacancy(vacancy, target_keywords, role_taxonomy, excluded_roles):

    search_text = get_search_text(vacancy)

    for category, keywords in target_keywords.items():
        vacancy[category] = find_keywords(search_text, keywords)

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


def classify_vacancies(vacancies, target_keywords, role_taxonomy, excluded_roles):
    return [
        classify_vacancy(vacancy, target_keywords, role_taxonomy, excluded_roles)
        for vacancy in vacancies
    ]