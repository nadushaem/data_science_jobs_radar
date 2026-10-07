from pipeline.keywords import ROLE_RENAMES
from storage.db import connect, from_json, now_iso, to_json


# старые ключи ролей переводим на новые при чтении
def _migrate_roles(roles):
    return sorted({ROLE_RENAMES.get(role, role) for role in roles or []})


def load_subscribers():
    with connect() as conn:
        rows = conn.execute(
            "SELECT chat_id, industries, roles FROM subscribers WHERE status = 'active'"
        ).fetchall()

    return {
        row["chat_id"]: {
            "industries": from_json(row["industries"], []),
            "roles": _migrate_roles(from_json(row["roles"], [])),
        }
        for row in rows
    }


def add_subscriber(subscribers, chat_id):
    now = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO subscribers (chat_id, created_at, updated_at) VALUES (?, ?, ?)
            ON CONFLICT (chat_id) DO UPDATE SET
                industries = '[]', roles = '[]', status = 'active', updated_at = excluded.updated_at
            """,
            (chat_id, now, now),
        )
    subscribers[chat_id] = {"industries": [], "roles": []}


def remove_subscriber(subscribers, chat_id):
    with connect() as conn:
        conn.execute(
            "UPDATE subscribers SET status = 'stopped', updated_at = ? WHERE chat_id = ?",
            (now_iso(), chat_id),
        )
    subscribers.pop(chat_id, None)


def _set_filter(subscribers, chat_id, column, values):
    values = sorted(set(values))
    with connect() as conn:
        conn.execute(
            f"UPDATE subscribers SET {column} = ?, updated_at = ? WHERE chat_id = ?",
            (to_json(values), now_iso(), chat_id),
        )
    subscribers[chat_id][column] = values


def get_industries(subscribers, chat_id):
    return subscribers[chat_id].get("industries") or []


def set_industries(subscribers, chat_id, industries):
    _set_filter(subscribers, chat_id, "industries", industries)


def get_roles(subscribers, chat_id):
    return subscribers[chat_id].get("roles") or []


def set_roles(subscribers, chat_id, roles):
    _set_filter(subscribers, chat_id, "roles", roles)
