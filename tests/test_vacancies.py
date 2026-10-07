import pandas as pd

from storage import vacancies as vac
from storage.db import connect


def _target(url):
    return {
        "url": url, "title": "data scientist", "published_at": pd.Timestamp("2026-10-01"),
        "skills": ["python"], "matched_roles": ["data_scientist"], "fintech": ["банк"],
        "salary_min_rub": 250_000.0, "salary_max_rub": float("nan"),
    }  # fmt: skip


def _complete(urls):
    run_id = vac.start_run()
    vac.complete_run(run_id, pd.DataFrame([_target(url) for url in urls]), n_raw=10, n_deduped=8)
    return run_id


def test_target_roundtrip():
    run_id = _complete(["u1"])
    row = vac.load_target_vacancies(latest=True).iloc[0]

    assert row["skills"] == ["python"] and row["duplicate_urls"] == []
    assert row["industries"] == {"fintech": ["банк"]}
    assert row["fintech"] and not row["edtech"]  # сферы снова bool-колонки
    assert row["published_at"] == pd.Timestamp("2026-10-01")
    assert row["salary_min_rub"] == 250_000 and pd.isna(row["salary_max_rub"])

    with connect() as conn:
        run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert (run["status"], run["n_raw"], run["n_deduped"], run["n_target"]) == ("ok", 10, 8, 1)


def test_latest_is_last_ok_run_and_archive_keeps_all():
    _complete(["u1", "u2"])
    _complete(["u2"])
    vac.fail_run(vac.start_run())  # упавший прогон снэпшот не меняет

    assert list(vac.load_target_vacancies(latest=True)["url"]) == ["u2"]
    assert set(vac.load_target_vacancies()["url"]) == {"u1", "u2"}


def test_archive_targets_does_not_touch_snapshot():
    _complete(["u1"])
    vac.archive_targets(pd.DataFrame([_target("u1"), _target("old")]))

    assert list(vac.load_target_vacancies(latest=True)["url"]) == ["u1"]
    assert set(vac.load_target_vacancies()["url"]) == {"u1", "old"}


def test_empty_database_gives_empty_snapshot():
    assert vac.load_target_vacancies(latest=True).empty


def test_raw_vacancies_keep_first_seen():
    vac.save_raw_vacancies([{"url": "u1", "source": "fake", "title": "старый"}])
    with connect() as conn:  # делаем вид, что впервые увидели вакансию 1 октября
        conn.execute("UPDATE vacancies SET first_seen_at = '2026-10-01', last_seen_at = ''")

    updated = {"url": "u1", "source": "fake", "title": "новый"}
    vac.save_raw_vacancies([updated, {"title": "без url"}])

    with connect() as conn:
        rows = conn.execute("SELECT * FROM vacancies").fetchall()
    assert len(rows) == 1  # вакансия без url не записалась
    assert rows[0]["title"] == "новый" and rows[0]["first_seen_at"] == "2026-10-01"
    assert rows[0]["last_seen_at"] > "2026-10-01"


def test_raw_snapshot_restores_dates():
    published_at = pd.Timestamp("2026-10-01 10:30")
    vac.save_raw_vacancies([{"url": "u1", "source": "fake", "published_at": published_at}])

    snapshot = vac.load_raw_vacancies("2000-01-01", "2100-01-01")
    assert snapshot["published_at"].tolist() == [published_at]
    assert vac.load_raw_vacancies("2000-01-01", "2000-01-02").empty
