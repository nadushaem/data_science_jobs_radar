import pandas as pd

from pipeline.keywords import TARGET_KEYWORDS
from storage.db import connect, from_json, now_iso, to_json

TEXT_COLUMNS = ["url", "title", "company", "location", "work_format", "source"]
JSON_COLUMNS = ["specialization", "level", "skills"]  # json или NULL
LIST_COLUMNS = ["matched_roles", "duplicate_urls"]  # NOT NULL в схеме: пустой список, а не NULL
TARGET_COLUMNS = [
    *TEXT_COLUMNS, *JSON_COLUMNS, *LIST_COLUMNS, "published_at", "salary_min_rub",
    "salary_max_rub", "industries", "last_run_id",
]  # fmt: skip

# upsert целевой вакансии. имена колонок — константы модуля, поэтому собрать sql f-строкой можно.
# last_run_id = None (дозапись архива из collect_history) не перетирает уже записанный прогон
_UPSERT_TARGET = f"""
INSERT INTO target_vacancies ({", ".join(TARGET_COLUMNS)})
VALUES ({", ".join(f":{column}" for column in TARGET_COLUMNS)})
ON CONFLICT (url) DO UPDATE SET
    {", ".join(f"{column} = excluded.{column}" for column in TARGET_COLUMNS[1:-1])},
    last_run_id = coalesce(excluded.last_run_id, last_run_id)
"""


# pd.NA / NaN / NaT → None: sqlite такие значения не понимает
def _scalar(value):
    if value is None or isinstance(value, list | dict):
        return value
    return None if pd.isna(value) else value


def _json_or_none(value):
    value = _scalar(value)
    return None if value is None else to_json(value)


def _int_or_none(value):
    value = _scalar(value)
    return None if value is None else int(value)


# строка классифицированного датафрейма → параметры для _UPSERT_TARGET
def _target_row(record, run_id):
    row = {column: _scalar(record.get(column)) for column in TEXT_COLUMNS}
    row.update({column: _json_or_none(record.get(column)) for column in JSON_COLUMNS})
    row.update({column: to_json(_scalar(record.get(column)) or []) for column in LIST_COLUMNS})

    published_at = _scalar(record.get("published_at"))
    row["published_at"] = None if published_at is None else pd.Timestamp(published_at).isoformat()
    row["salary_min_rub"] = _int_or_none(record.get("salary_min_rub"))
    row["salary_max_rub"] = _int_or_none(record.get("salary_max_rub"))

    # из колонок-сфер сохраняем только сработавшие: сфера → найденные ключевые слова.
    # _scalar нужен из-за NaN: bool(nan) == True, и без него сфера «сработала» бы на пустом месте
    industries = {key: _scalar(record.get(key)) for key in TARGET_KEYWORDS}
    row["industries"] = to_json({key: value for key, value in industries.items() if value})
    row["last_run_id"] = run_id
    return row


# === прогоны ===


def start_run():
    with connect() as conn:
        return conn.execute("INSERT INTO runs (started_at) VALUES (?)", (now_iso(),)).lastrowid


def fail_run(run_id):
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = 'failed', finished_at = ? WHERE run_id = ?",
            (now_iso(), run_id),
        )


# целевые вакансии и статус прогона пишем в одной транзакции: бот видит
# либо предыдущий снэпшот целиком, либо новый целиком, но не половину
def complete_run(run_id, target_df, n_raw, n_deduped):
    rows = [_target_row(record, run_id) for record in target_df.to_dict("records")]
    with connect() as conn:
        conn.executemany(_UPSERT_TARGET, rows)
        conn.execute(
            """
            UPDATE runs SET status = 'ok', finished_at = ?, n_raw = ?, n_deduped = ?, n_target = ?
            WHERE run_id = ?
            """,
            (now_iso(), n_raw, n_deduped, len(rows), run_id),
        )


# дозапись архива статистики (collect_history) без влияния на снэпшот бота
def archive_targets(target_df):
    rows = [_target_row(record, None) for record in target_df.to_dict("records")]
    with connect() as conn:
        conn.executemany(_UPSERT_TARGET, rows)


# === сырой слой ===


# вакансии как их отдал источник. first_seen_at ставится один раз,
# last_seen_at и payload обновляются при каждой новой встрече url
def save_raw_vacancies(vacancies):
    now = now_iso()
    rows = [
        {
            "url": vacancy["url"],
            "source": vacancy.get("source"),
            "title": vacancy.get("title"),
            "company": vacancy.get("company"),
            "payload": to_json(vacancy),
            "now": now,
        }
        for vacancy in vacancies
        if vacancy.get("url")
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO vacancies
                (url, source, title, company, payload, first_seen_at, last_seen_at)
            VALUES (:url, :source, :title, :company, :payload, :now, :now)
            ON CONFLICT (url) DO UPDATE SET
                title = excluded.title, company = excluded.company,
                payload = excluded.payload, last_seen_at = excluded.last_seen_at
            """,
            rows,
        )


# снапшот для разметки: сырые вакансии, впервые увиденные в [since, until)
def load_raw_vacancies(since, until):
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM vacancies WHERE first_seen_at >= ? AND first_seen_at < ? "
            "ORDER BY first_seen_at",
            (since, until),
        ).fetchall()

    df = pd.DataFrame([from_json(row["payload"]) for row in rows])
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], format="ISO8601", errors="coerce")
    return df


# === чтение целевых вакансий ===


# latest=True — снэпшот последнего успешного прогона (то, что видит бот),
# latest=False — весь архив (статистика навыков)
def load_target_vacancies(latest=False):
    query = "SELECT * FROM target_vacancies"
    if latest:
        query += " WHERE last_run_id = (SELECT max(run_id) FROM runs WHERE status = 'ok')"

    with connect() as conn:
        rows = conn.execute(query + " ORDER BY published_at DESC").fetchall()

    records = []
    for row in rows:
        record = dict(row)
        record.update({column: from_json(record[column]) for column in JSON_COLUMNS + LIST_COLUMNS})
        record["industries"] = from_json(record["industries"], {})
        # снаружи сферы — bool-колонки, как раньше в pkl: summary.py и stats.py не меняются
        record.update({key: key in record["industries"] for key in TARGET_KEYWORDS})
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df["published_at"] = pd.to_datetime(df["published_at"], format="ISO8601", errors="coerce")
    df["is_target"] = True
    return df
