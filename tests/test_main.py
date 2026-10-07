import pandas as pd
import pytest

import main
from storage.db import connect


class _FakeSource:
    SOURCE_NAME = "fake"

    @staticmethod
    def fetch_vacancies(days):
        return [
            {"url": "https://x/1", "source": "fake", "title": "Data Scientist", "company": "Банк",
             "description": "финтех, платежные системы", "published_at": pd.Timestamp("2026-10-01")}
        ]  # fmt: skip


# весь прогон на настоящей временной базе: источники и телеграм подменены
def test_run_saves_snapshot_and_sends_it(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # vacancies_classify.csv пишется в data/ временной папки
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(main, "SOURCES", [_FakeSource])
    monkeypatch.setattr(main, "get_exchange_rates", lambda: {"RUB": 1.0})
    sent = []
    monkeypatch.setattr(main, "send_summary", sent.append)

    main.run()

    assert list(sent[0]["url"]) == ["https://x/1"]
    with connect() as conn:
        run = conn.execute("SELECT status, n_raw, n_target FROM runs").fetchone()
        raw_count = conn.execute("SELECT count(*) FROM vacancies").fetchone()[0]
    assert tuple(run) == ("ok", 1, 1)
    assert raw_count == 1


def test_failed_run_is_marked(monkeypatch):
    def _broken(run_id):
        raise RuntimeError("парсер сломался")

    monkeypatch.setattr(main, "collect", _broken)

    with pytest.raises(RuntimeError):
        main.run()
    with connect() as conn:
        assert conn.execute("SELECT status FROM runs").fetchone()[0] == "failed"
