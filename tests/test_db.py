import sqlite3

import pytest

from storage import db

TABLES = {"subscribers", "deliveries", "bot_state", "datasecrets_seen", "runs", "vacancies"}


def test_init_db_creates_schema_and_is_idempotent():
    db.init_db()  # фикстура уже вызвала init_db, второй вызов ничего не должен ломать

    with db.connect() as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert TABLES | {"target_vacancies"} <= tables
    assert version == len(db.MIGRATIONS)
    assert mode == "wal"


def test_connect_rolls_back_on_error():
    with pytest.raises(RuntimeError), db.connect() as conn:
        conn.execute("INSERT INTO bot_state VALUES ('offset', '1')")
        raise RuntimeError("упали посреди транзакции")

    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM bot_state").fetchone()[0] == 0


def test_foreign_keys_are_checked():
    with pytest.raises(sqlite3.IntegrityError), db.connect() as conn:
        conn.execute("INSERT INTO deliveries (chat_id, url, sent_at) VALUES (1, 'u', 't')")


def test_json_helpers():
    assert db.from_json(db.to_json(["финтех", "ml"])) == ["финтех", "ml"]
    assert db.from_json(None, default=[]) == []
