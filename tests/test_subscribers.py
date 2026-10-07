from bot import subscribers as subs
from storage.db import connect


def _status(chat_id):
    with connect() as conn:
        query = "SELECT status FROM subscribers WHERE chat_id = ?"
        row = conn.execute(query, (chat_id,)).fetchone()
    return row["status"]


def test_changes_are_saved_without_explicit_save():
    cache = {}
    subs.add_subscriber(cache, 42)
    subs.set_industries(cache, 42, ["fintech", "edtech", "fintech"])
    subs.set_roles(cache, 42, ["ml_engineer"])

    expected = {42: {"industries": ["edtech", "fintech"], "roles": ["ml_engineer"]}}
    assert cache == expected
    assert subs.load_subscribers() == expected


def test_stop_keeps_row_and_resubscribe_resets_filters():
    cache = {}
    subs.add_subscriber(cache, 42)
    subs.set_industries(cache, 42, ["fintech"])
    subs.remove_subscriber(cache, 42)

    assert cache == {}
    assert subs.load_subscribers() == {}
    assert _status(42) == "stopped"

    subs.add_subscriber(cache, 42)
    assert subs.load_subscribers() == {42: {"industries": [], "roles": []}}
    assert _status(42) == "active"


def test_renamed_roles_are_migrated_on_load():
    with connect() as conn:
        conn.execute(
            "INSERT INTO subscribers (chat_id, roles, created_at, updated_at) "
            "VALUES (42, '[\"ai_ml_engineer\"]', 't', 't')"
        )

    assert subs.load_subscribers()[42]["roles"] == ["ai_engineer"]
