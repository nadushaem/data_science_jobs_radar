# сделать алиасы для ролей, добавить стажер главный и тд, и все привести к тому как сделано у geekjob


import pandas as pd

from sources import geekjob, getmatch
from keywords import TARGET_KEYWORDS, EXCLUDED_ROLES, ROLE_TAXONOMY
from normalize import normalize_dataframe
from classify import classify_vacancies


SOURCES = [geekjob, getmatch]

vacancies = []

for source in SOURCES:
    try:
        source_vacancies = source.fetch_vacancies()
        vacancies.extend(source_vacancies)
        print(f"{source.SOURCE_NAME}: {len(source_vacancies)} вакансий")

    except Exception as error:
        print(f"Источник {source.SOURCE_NAME} упал: {error}")
        continue

df_raw = pd.DataFrame(vacancies)
df_raw = df_raw.replace(r"^\s*$", pd.NA, regex=True)
df_raw.to_csv("data/vacancies_raw.csv", index=False, encoding="utf-8-sig")

df = normalize_dataframe(df_raw)
df.to_csv("data/vacancies.csv", index=False, encoding="utf-8-sig")

df = pd.DataFrame(classify_vacancies(
    df.to_dict("records"),
    TARGET_KEYWORDS,
    ROLE_TAXONOMY,
    EXCLUDED_ROLES
))

df.to_csv("data/vacancies_classify.csv", index=False, encoding="utf-8-sig")

print(df.info())