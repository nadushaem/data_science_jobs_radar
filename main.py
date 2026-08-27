import pandas as pd
from apscheduler.schedulers.blocking import BlockingScheduler

from sources import geekjob, getmatch
from keywords import TARGET_KEYWORDS, EXCLUDED_ROLES, ROLE_TAXONOMY
from normalize import normalize_dataframe
from classify import classify_vacancies
from dedupe import deduplicate_vacancies
from summary import build_summary_messages
from telegram_bot import send_summary, poll_updates

from dotenv import load_dotenv
load_dotenv()


SOURCES = [geekjob, getmatch]


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

    target_df = df[df["is_target"]]

    try:
        send_summary(target_df)
    except Exception as error:
        print(f"Не удалось отправить сводку в telegram: {error}")


if __name__ == "__main__":
    run()

    scheduler = BlockingScheduler()
    scheduler.add_job(run, "interval", hours=4)
    scheduler.add_job(poll_updates, "interval", seconds=15)
    scheduler.start()