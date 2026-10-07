import pandas as pd
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from bot.api import delete_webhook
from bot.handlers import poll_updates, send_summary
from pipeline.classify import classify_vacancies
from pipeline.dedupe import deduplicate_vacancies
from pipeline.keywords import EXCLUDED_ROLES, INDUSTRY_EXCLUDES, ROLE_TAXONOMY, TARGET_KEYWORDS
from pipeline.normalize import normalize_dataframe
from pipeline.stats import add_rub_salaries, get_exchange_rates
from sources import datasecrets, geekjob, getmatch, hirify
from storage.db import init_db
from storage.vacancies import (
    complete_run,
    fail_run,
    load_target_vacancies,
    save_raw_vacancies,
    start_run,
)

load_dotenv()


SOURCES = [datasecrets, geekjob, getmatch, hirify]


# сбор, обработка и запись в базу одного прогона
def collect(run_id):
    vacancies = []

    for source in SOURCES:
        try:
            source_vacancies = source.fetch_vacancies(days=7)
            vacancies.extend(source_vacancies)
            print(f"{source.SOURCE_NAME}: {len(source_vacancies)} вакансий")

        except Exception as error:
            print(f"Источник {source.SOURCE_NAME} упал: {error}")
            continue

    save_raw_vacancies(vacancies)  # сырой слой — до любой обработки

    df_raw = pd.DataFrame(vacancies)
    df_raw = df_raw.replace(r"^\s*$", pd.NA, regex=True)

    df = normalize_dataframe(df_raw)
    df = deduplicate_vacancies(df)

    records = classify_vacancies(
        df.to_dict("records"), TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES, INDUSTRY_EXCLUDES
    )
    df = pd.DataFrame(records)
    df.to_csv("data/vacancies_classify.csv", index=False, encoding="utf-8-sig")  # для отладки

    target_df = add_rub_salaries(df[df["is_target"]], get_exchange_rates())
    complete_run(run_id, target_df, n_raw=len(df_raw), n_deduped=len(df))


def run():
    run_id = start_run()

    try:
        collect(run_id)
    except Exception:
        fail_run(run_id)
        raise  # дальше все как раньше: ошибка видна в журнале

    try:
        # рассылаем снэпшот из базы — ровно его же потом покажет /view_all
        send_summary(load_target_vacancies(latest=True))
    except Exception as error:
        print(f"Не удалось отправить сводку в telegram: {error}")


if __name__ == "__main__":
    init_db()  # создает базу или доводит схему до последней версии
    delete_webhook()

    run()

    scheduler = BlockingScheduler()
    scheduler.add_job(run, "interval", hours=4)
    scheduler.add_job(poll_updates, "interval", seconds=15)
    scheduler.start()
