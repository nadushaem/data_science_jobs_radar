from storage.db import connect, now_iso

# журнал отправок живет в таблице deliveries и никогда не чистится.
# «уже отправленные» подписчику — только отправки после его history_reset_at


# url, которые подписчик уже видел
def get_seen_urls(chat_id):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.url
            FROM deliveries AS d
            JOIN subscribers AS s ON s.chat_id = d.chat_id
            WHERE d.chat_id = ? AND d.sent_at >= coalesce(s.history_reset_at, '')
            """,
            (chat_id,),
        ).fetchall()
    return {row["url"] for row in rows}


# все url вакансии: свой + url дублей с других бордов (см. dedupe.py)
def _vacancy_urls(row):
    duplicates = row.get("duplicate_urls")
    return [row.get("url"), *(duplicates if isinstance(duplicates, list) else [])]


def all_vacancy_urls(df):
    return [url for _, row in df.iterrows() for url in _vacancy_urls(row) if isinstance(url, str)]


# новые для подписчика вакансии — те, у которых ни один url (свой или дубля) еще не отправлялся
def get_new_vacancies_for_subscriber(target_df, seen_urls):
    if target_df.empty or not seen_urls:
        return target_df

    is_seen = target_df.apply(lambda row: bool(seen_urls.intersection(_vacancy_urls(row))), axis=1)
    return target_df[~is_seen]


# каждая отправка — новая строка; dict.fromkeys убирает повторы, сохраняя порядок
def mark_as_sent(chat_id, urls):
    now = now_iso()
    rows = [(chat_id, url, now) for url in dict.fromkeys(urls) if url]
    with connect() as conn:
        conn.executemany("INSERT INTO deliveries (chat_id, url, sent_at) VALUES (?, ?, ?)", rows)


# при смене фильтров историю не удаляем, а отмечаем момент сброса
def reset_subscriber_history(chat_id):
    with connect() as conn:
        conn.execute(
            "UPDATE subscribers SET history_reset_at = ? WHERE chat_id = ?", (now_iso(), chat_id)
        )
