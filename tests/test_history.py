from datetime import datetime, timedelta

import pandas as pd

from bot import history


def _iso(days_ago):
    return (datetime.now() - timedelta(days=days_ago)).isoformat()


def test_prune_drops_old_urls_and_empty_subscribers():
    sent = {"1": {"old": _iso(40), "new": _iso(1)}, "2": {"old": _iso(40)}}
    assert history.prune_sent_vacancies(sent) == {"1": {"new": sent["1"]["new"]}}


def test_new_vacancies_are_personal():
    df = pd.DataFrame({"url": ["a", "b", "c"]})
    sent = history.mark_as_sent({}, 42, ["a", None])  # пустые url не пишем

    assert list(history.get_new_vacancies_for_subscriber(df, sent, 42)["url"]) == ["b", "c"]
    # у другого подписчика своя история
    assert len(history.get_new_vacancies_for_subscriber(df, sent, 7)) == 3


def test_reset_history():
    sent = history.mark_as_sent({}, 42, ["a"])
    assert history.reset_subscriber_history(sent, 42) == {}


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "SENT_FILE", str(tmp_path / "data" / "sent.json"))
    sent = history.mark_as_sent({}, 42, ["a"])

    history.save_sent_vacancies(sent)
    assert history.load_sent_vacancies() == sent
