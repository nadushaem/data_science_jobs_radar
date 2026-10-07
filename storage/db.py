import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DEFAULT_DB_PATH = "data/radar.db"

SCHEMA_V1 = """
-- подписчики: одна строка на чат, при /stop меняется status, строка остается
CREATE TABLE subscribers (
    chat_id          INTEGER PRIMARY KEY,
    industries       TEXT NOT NULL DEFAULT '[]',     -- json-список ключей сфер
    roles            TEXT NOT NULL DEFAULT '[]',     -- json-список ключей ролей
    status           TEXT NOT NULL DEFAULT 'active', -- active / stopped / blocked
    history_reset_at TEXT,  -- отправки раньше этого момента не считаются «уже виденными»
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

-- журнал отправок: каждая отправка — отдельная строка, ничего не удаляем
CREATE TABLE deliveries (
    delivery_id INTEGER PRIMARY KEY,
    chat_id     INTEGER NOT NULL REFERENCES subscribers (chat_id),
    url         TEXT NOT NULL,
    sent_at     TEXT NOT NULL
);
CREATE INDEX idx_deliveries_chat ON deliveries (chat_id, sent_at);

-- служебные значения
CREATE TABLE bot_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- у datasecrets нет дат публикации — храним, когда впервые увидели вакансию
CREATE TABLE datasecrets_seen (vacancy_id TEXT PRIMARY KEY, first_seen_at TEXT NOT NULL);

-- журнал прогонов пайплайна
CREATE TABLE runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running', -- running / ok / failed
    n_raw INTEGER, n_deduped INTEGER, n_target INTEGER
);

-- все вакансии как их отдал источник, без обработки
CREATE TABLE vacancies (
    url           TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    title         TEXT,
    company       TEXT,
    payload       TEXT NOT NULL, -- весь сырой словарь из источника, json
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL
);
CREATE INDEX idx_vacancies_first_seen ON vacancies (first_seen_at);

-- целевые вакансии после классификации
CREATE TABLE target_vacancies (
    url TEXT PRIMARY KEY,
    title TEXT, company TEXT, location TEXT, work_format TEXT, source TEXT,
    published_at TEXT, specialization TEXT,
    level TEXT, skills TEXT,                    -- json-списки
    salary_min_rub INTEGER, salary_max_rub INTEGER,
    industries     TEXT NOT NULL DEFAULT '{}',  -- json: сфера → сработавшие ключевые слова
    matched_roles  TEXT NOT NULL DEFAULT '[]',  -- json-список
    duplicate_urls TEXT NOT NULL DEFAULT '[]',  -- json-список
    last_run_id    INTEGER REFERENCES runs (run_id)
);
CREATE INDEX idx_target_last_run ON target_vacancies (last_run_id);
"""

# миграции по порядку: i-я переводит базу с версии i на i + 1.
# выкаченные на сервер миграции не правим — новые изменения только дописываем в конец
MIGRATIONS = [SCHEMA_V1]


def db_path():
    return os.environ.get("DB_PATH", DEFAULT_DB_PATH)


# соединение на одну операцию: коммит при успехе, откат при ошибке, закрытие всегда
@contextmanager
def connect():
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # сколько ждать, если базу сейчас пишет другой поток
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # по умолчанию sqlite их не проверяет

    try:
        with conn:
            yield conn
    finally:
        conn.close()


# создает базу или доводит ее схему до последней версии. безопасно вызывать много раз
def init_db():
    with connect() as conn:
        # wal: чтение не ждёт записи. режим сохраняется в самом файле базы
        conn.execute("PRAGMA journal_mode = WAL")
        version = conn.execute("PRAGMA user_version").fetchone()[0]

        # каждая миграция вместе с номером версии — в одной транзакции: либо целиком, либо никак
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")


def now_iso():
    return datetime.now().isoformat()


def to_json(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def from_json(text, default=None):
    return json.loads(text) if text else default
