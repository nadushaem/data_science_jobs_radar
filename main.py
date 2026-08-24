import requests
import pandas as pd
from bs4 import BeautifulSoup

from functions import (
    parse_card, get_vacancy_soup, parse_description, parse_tags, get_search_text,
    find_keywords, find_roles, find_excluded_roles
)
from keywords import TARGET_KEYWORDS, TARGET_ROLES, EXCLUDED_ROLES


base_url = "https://geekjob.ru/vacancies"

vacancies = []

for page in range(1, 6):
    url = f"{base_url}/{page}"

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    cards = soup.find_all("li",class_="collection-item avatar")

    for card in cards:
        vacancy = parse_card(card, base_url)

        try:
            vacancy_soup = get_vacancy_soup(vacancy["url"])
            vacancy["description"] = parse_description(vacancy_soup)
            tags = parse_tags(vacancy_soup)
            vacancy.update(tags)

        except requests.RequestException as error:
            print(f"Ошибка: {vacancy['title']}")
            print(error)

            vacancy["description"] = None
            vacancy["specialization"] = None
            vacancy["industry"] = None
            vacancy["level"] = None

        vacancies.append(vacancy)

for vacancy in vacancies:
    search_text = get_search_text(vacancy)
    for category, keywords in TARGET_KEYWORDS.items():
        vacancy[category] = find_keywords(search_text, keywords)

    vacancy["matched_roles"] = find_roles(vacancy["title"], TARGET_ROLES)
    vacancy["excluded_roles"] = find_excluded_roles(vacancy["title"], EXCLUDED_ROLES)

df = pd.DataFrame(vacancies)
df = df.replace(r"^\s*$", pd.NA, regex=True)
df.to_csv("vacancies.csv", index=False, encoding="utf-8-sig")

for vacancy in vacancies:
    if vacancy["matched_roles"] or vacancy["excluded_roles"]:
        print(
            vacancy["title"],
            "| target:", vacancy["matched_roles"],
            "| excluded:", vacancy["excluded_roles"]
        )

