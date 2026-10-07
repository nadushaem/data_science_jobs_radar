import json

import pandas as pd

import migrate_to_sqlite as migration
from bot.history import get_seen_urls
from bot.subscribers import load_subscribers
from storage.db import connect
from storage.vacancies import load_target_vacancies


# файлы в том виде, в каком их писала старая версия бота
def _write_old_files(data_dir):
    data_dir.mkdir()
    subscribers = {"42": {"industries": ["fintech"], "roles": ["ai_ml_engineer"]}}
    # 7 уже отписался, но остался в истории рассылок
    sent = {"42": {"u1": "2026-09-20T10:00:00"}, "7": {"u2": "2026-09-01T10:00:00"}}
    (data_dir / "subscribers.json").write_text(json.dumps(subscribers), encoding="utf-8")
    (data_dir / "sent_vacancies.json").write_text(json.dumps(sent), encoding="utf-8")
    (data_dir / "datasecrets_seen.json").write_text('{"abc": "2026-09-15T08:00:00"}', "utf-8")
    (data_dir / "telegram_offset.txt").write_text("1001", encoding="utf-8")

    stats = pd.DataFrame([
        {"url": "u1", "skills": ["python"], "salary_min": 200_000.0, "salary_max": None,
         "matched_roles": ["ai_ml_engineer"], "fintech": True, "edtech": False},
    ])  # fmt: skip
    stats.to_pickle(data_dir / "vacancies_stats.pkl")


def test_migration_moves_everything_and_is_idempotent(tmp_path):
    data_dir = tmp_path / "old"
    _write_old_files(data_dir)

    assert migration.migrate(data_dir) == 0
    assert migration.migrate(data_dir) == 0  # повторный запуск ничего не дублирует

    assert load_subscribers() == {42: {"industries": ["fintech"], "roles": ["ai_engineer"]}}
    assert get_seen_urls(42) == {"u1"} and get_seen_urls(7) == {"u2"}

    with connect() as conn:
        count = conn.execute("SELECT count(*) FROM deliveries").fetchone()[0]
        status = conn.execute("SELECT status FROM subscribers WHERE chat_id = 7").fetchone()[0]
        offset = conn.execute("SELECT value FROM bot_state").fetchone()[0]
        seen = conn.execute("SELECT first_seen_at FROM datasecrets_seen").fetchone()[0]
    assert (count, status, offset, seen) == (2, "stopped", "1001", "2026-09-15T08:00:00")

    archive = load_target_vacancies()
    assert archive.loc[0, "salary_min_rub"] == 200_000 and archive.loc[0, "fintech"]
    assert archive.loc[0, "matched_roles"] == ["ai_engineer"] and not archive.loc[0, "edtech"]
    assert load_target_vacancies(latest=True).empty  # архив не попадает в снэпшот бота


def test_old_list_format_and_missing_files(tmp_path):
    data_dir = tmp_path / "old"
    data_dir.mkdir()
    (data_dir / "subscribers.json").write_text("[42, 7]", encoding="utf-8")

    assert migration.migrate(data_dir) == 0
    assert load_subscribers() == {
        42: {"industries": [], "roles": []},
        7: {"industries": [], "roles": []},
    }
