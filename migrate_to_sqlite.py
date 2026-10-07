# разовый перенос данных из json / pkl в sqlite. запуск из корня проекта:
#   python migrate_to_sqlite.py                            — data/ → база из DB_PATH (data/radar.db)
#   python migrate_to_sqlite.py --data-dir data/prod_copy  — репетиция на копии прод-данных
# повторный запуск безопасен: уже перенесённое не дублируется, исходные файлы не меняются

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from bot.subscribers import load_subscribers
from pipeline.keywords import ROLE_RENAMES
from storage.db import connect, db_path, init_db, now_iso, to_json
from storage.vacancies import archive_targets


def _read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _rename_roles(roles):
    return sorted({ROLE_RENAMES.get(role, role) for role in roles or []})


# старый формат subscribers.json — просто список chat_id без фильтров
def read_subscribers(data_dir):
    raw = _read_json(data_dir / "subscribers.json", {})
    if isinstance(raw, list):
        raw = {chat_id: {} for chat_id in raw}

    return {
        int(chat_id): {
            "industries": sorted(data.get("industries") or []),
            "roles": _rename_roles(data.get("roles")),
        }
        for chat_id, data in raw.items()
    }


# отписавшиеся остались в истории рассылок — заводим их со статусом stopped.
# created_at — первая известная отправка (история в json хранилась 30 дней)
def _subscriber_row(chat_id, subscribers, sent, now):
    data = subscribers.get(chat_id, {"industries": [], "roles": []})
    status = "active" if chat_id in subscribers else "stopped"
    created_at = min(sent.get(chat_id, {}).values(), default=now)
    return (chat_id, to_json(data["industries"]), to_json(data["roles"]), status, created_at, now)


# подписчики, история рассылок, offset и datasecrets_seen — одной транзакцией
def migrate_bot_state(data_dir, subscribers, sent, seen):
    now = now_iso()
    offset_file = data_dir / "telegram_offset.txt"
    chat_ids = subscribers.keys() | sent.keys()

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO subscribers (chat_id, industries, roles, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (chat_id) DO NOTHING
            """,
            [_subscriber_row(chat_id, subscribers, sent, now) for chat_id in chat_ids],
        )

        # у deliveries нет уникального ключа, поэтому вставляем, только если такой строки ещё нет
        conn.executemany(
            """
            INSERT INTO deliveries (chat_id, url, sent_at)
            SELECT :chat_id, :url, :sent_at
            WHERE NOT EXISTS (
                SELECT 1 FROM deliveries
                WHERE chat_id = :chat_id AND url = :url AND sent_at = :sent_at
            )
            """,
            [
                {"chat_id": chat_id, "url": url, "sent_at": sent_at}
                for chat_id, urls in sent.items()
                for url, sent_at in urls.items()
            ],
        )

        conn.executemany(
            "INSERT INTO datasecrets_seen VALUES (?, ?) ON CONFLICT (vacancy_id) DO NOTHING",
            list(seen.items()),
        )

        if offset_file.exists():
            offset = offset_file.read_text(encoding="utf-8").strip() or "0"
            conn.execute(
                "INSERT INTO bot_state VALUES ('telegram_offset', ?) ON CONFLICT (key) DO NOTHING",
                (offset,),
            )


# архив статистики: зарплаты в pkl уже в рублях, сферы — bool-колонки
def migrate_stats(data_dir):
    path = data_dir / "vacancies_stats.pkl"
    if not path.exists():
        return 0

    stats = pd.read_pickle(path).dropna(subset=["url"]).drop_duplicates(subset=["url"], keep="last")
    stats = stats.rename(columns={"salary_min": "salary_min_rub", "salary_max": "salary_max_rub"})
    if "matched_roles" in stats.columns:
        stats["matched_roles"] = stats["matched_roles"].map(
            lambda roles: _rename_roles(roles) if isinstance(roles, list) else []
        )

    # то, что уже есть в базе, не перетираем старыми данными
    with connect() as conn:
        existing = {row["url"] for row in conn.execute("SELECT url FROM target_vacancies")}
    archive_targets(stats[~stats["url"].isin(existing)])
    return len(stats)


def _count(query):
    with connect() as conn:
        return conn.execute(query).fetchone()[0]


# сверка: в базе должно оказаться не меньше, чем было в файлах, а фильтры — совпасть
def verify(subscribers, sent, seen, n_stats):
    n_sent = sum(len(urls) for urls in sent.values())
    checks = [
        ("подписчики (active)", len(subscribers),
         _count("SELECT count(*) FROM subscribers WHERE status = 'active'")),
        ("история рассылок", n_sent, _count("SELECT count(*) FROM deliveries")),
        ("datasecrets_seen", len(seen), _count("SELECT count(*) FROM datasecrets_seen")),
        ("архив статистики", n_stats, _count("SELECT count(*) FROM target_vacancies")),
    ]  # fmt: skip

    problems = 0
    for name, in_files, in_db in checks:
        mark = "ok" if in_db >= in_files else "МЕНЬШЕ, ЧЕМ В ФАЙЛАХ"
        problems += in_db < in_files
        print(f"{name:<22} файлы {in_files:>6} → база {in_db:>6}  {mark}")

    actual = load_subscribers()
    wrong = [chat_id for chat_id, data in subscribers.items() if actual.get(chat_id) != data]
    if wrong:
        print(f"не совпали фильтры у подписчиков: {wrong}")

    return problems + len(wrong)


def migrate(data_dir):
    init_db()
    print(f"база: {db_path()}, исходные файлы: {data_dir}")

    subscribers = read_subscribers(data_dir)
    raw_sent = _read_json(data_dir / "sent_vacancies.json", {})
    sent = {int(chat_id): urls for chat_id, urls in raw_sent.items()}
    seen = _read_json(data_dir / "datasecrets_seen.json", {})

    migrate_bot_state(data_dir, subscribers, sent, seen)
    n_stats = migrate_stats(data_dir)

    problems = verify(subscribers, sent, seen, n_stats)
    print("перенос прошёл без расхождений" if not problems else f"расхождений: {problems}")
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="перенос данных из json / pkl в sqlite")
    parser.add_argument("--data-dir", default="data", type=Path)
    sys.exit(1 if migrate(parser.parse_args().data_dir) else 0)
