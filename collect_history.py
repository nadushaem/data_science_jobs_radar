# запуск: python collect_history.py

import pandas as pd

from sources import geekjob, getmatch
from keywords import TARGET_KEYWORDS, EXCLUDED_ROLES, ROLE_TAXONOMY
from normalize import normalize_dataframe
from classify import classify_vacancies
from dedupe import deduplicate_vacancies
from stats import build_stats_dataset, append_stats, get_exchange_rates

from dotenv import load_dotenv
load_dotenv()


SOURCES = [geekjob, getmatch]


# разовый прогон: собираем вакансии за месяц и кладем в архив статистики.
# дальше main.py будет дописывать туда свежие вакансии
def run(days=30):
    vacancies = []

    for source in SOURCES:
        try:
            source_vacancies = source.fetch_vacancies(days=days)
            vacancies.extend(source_vacancies)
            print(f"{source.SOURCE_NAME}: {len(source_vacancies)} вакансий")
        except Exception as error:
            print(f"источник {source.SOURCE_NAME} упал: {error}")
            continue

    df = pd.DataFrame(vacancies)
    df = df.replace(r"^\s*$", pd.NA, regex=True)

    df = normalize_dataframe(df)
    df = deduplicate_vacancies(df)

    df = pd.DataFrame(
        classify_vacancies(df.to_dict("records"), TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES)
    )

    for category in ["healthtech", "medtech", "femtech", "fintech", "edtech",
                     "hrtech", "adtech", "gamedev", "logistics", "ecommerce"]:
        df[category] = df[category].astype(bool)

    rates = get_exchange_rates()
    stats_df = build_stats_dataset(df, rates)

    archive = append_stats(stats_df)
    print(f"в архиве статистики теперь {len(archive)} вакансий")


if __name__ == "__main__":
    run()