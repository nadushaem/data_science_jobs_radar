import pandas as pd
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from bot.api import delete_webhook
from bot.handlers import poll_updates, send_summary
from pipeline.classify import classify_vacancies
from pipeline.dedupe import deduplicate_vacancies
from pipeline.keywords import EXCLUDED_ROLES, ROLE_TAXONOMY, TARGET_KEYWORDS
from pipeline.normalize import normalize_dataframe
from pipeline.stats import append_stats, build_stats_dataset, get_exchange_rates
from sources import datasecrets, geekjob, getmatch, hirify

load_dotenv()


SOURCES = [datasecrets, geekjob, getmatch, hirify]


def run():
    vacancies = []

    for source in SOURCES:
        try:
            source_vacancies = source.fetch_vacancies(days=7)
            vacancies.extend(source_vacancies)
            print(f"{source.SOURCE_NAME}: {len(source_vacancies)} вакансий")

        except Exception as error:
            print(f"Источник {source.SOURCE_NAME} упал: {error}")
            continue

    df_raw = pd.DataFrame(vacancies)
    df_raw = df_raw.replace(r"^\s*$", pd.NA, regex=True)
    df_raw.to_csv("data/vacancies_raw.csv", index=False, encoding="utf-8-sig")

    df = normalize_dataframe(df_raw)
    df = deduplicate_vacancies(df)

    df = pd.DataFrame(classify_vacancies(df.to_dict("records"), TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES))
    df.to_csv("data/vacancies_classify.csv", index=False, encoding="utf-8-sig")

    try:
        rates = get_exchange_rates()
        stats_df = build_stats_dataset(df, rates)
        append_stats(stats_df)
    except Exception as error:
        print(f"не удалось обновить архив статистики: {error}")

    target_df = df[df["is_target"]]

    target_df.to_pickle("data/vacancies_latest.pkl")

    try:
        send_summary(target_df)
    except Exception as error:
        print(f"Не удалось отправить сводку в telegram: {error}")


if __name__ == "__main__":
    delete_webhook()

    run()

    scheduler = BlockingScheduler()
    scheduler.add_job(run, "interval", hours=4)
    scheduler.add_job(poll_updates, "interval", seconds=15)
    scheduler.start()