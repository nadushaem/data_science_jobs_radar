# запуск: python collect_history.py

import pandas as pd
from dotenv import load_dotenv

from pipeline.classify import classify_vacancies
from pipeline.dedupe import deduplicate_vacancies
from pipeline.keywords import EXCLUDED_ROLES, INDUSTRY_EXCLUDES, ROLE_TAXONOMY, TARGET_KEYWORDS
from pipeline.normalize import normalize_dataframe
from pipeline.stats import add_rub_salaries, get_exchange_rates
from sources import datasecrets, geekjob, getmatch, hirify
from storage.db import init_db
from storage.vacancies import archive_targets

load_dotenv()


SOURCES = [datasecrets, geekjob, getmatch, hirify]


# разовый прогон: собираем вакансии за месяц и кладем в архив статистики (target_vacancies).
# снэпшот бота и сырой слой не трогаем — дальше main.py будет дописывать свежие вакансии
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

    records = classify_vacancies(
        df.to_dict("records"), TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES, INDUSTRY_EXCLUDES
    )
    df = pd.DataFrame(records)

    target_df = add_rub_salaries(df[df["is_target"]], get_exchange_rates())
    archive_targets(target_df)
    print(f"в архив статистики записано {len(target_df)} вакансий")


if __name__ == "__main__":
    init_db()
    run()
