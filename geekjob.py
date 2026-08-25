import requests
import pandas as pd
from bs4 import BeautifulSoup

from functions import (
    parse_card, get_vacancy_soup, parse_description, parse_tags, get_search_text,
    find_keywords, find_excluded_roles
)
from keywords import TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES
from normalize import normalize_dataframe
from classify import classify_vacancies


base_url = "https://geekjob.ru/vacancies"

vacancies = []

for page in range(1, 10):
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

df_raw = pd.DataFrame(vacancies)
df_raw = df_raw.replace(r"^\s*$",pd.NA, regex=True,)
df_raw.to_csv("data/vacancies_raw.csv",index=False,encoding="utf-8-sig",)

df = normalize_dataframe(df_raw)
df.to_csv("data/vacancies.csv",index=False,encoding="utf-8-sig",)

df = pd.DataFrame(classify_vacancies(
    df.to_dict("records"),
    TARGET_KEYWORDS,
    ROLE_TAXONOMY,
    EXCLUDED_ROLES
))

df.to_csv("data/vacancies_classify.csv",index=False,encoding="utf-8-sig",)
