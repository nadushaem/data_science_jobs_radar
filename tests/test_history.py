import pandas as pd

from bot import history
from bot.subscribers import add_subscriber
from storage.db import connect


def _deliveries_count(chat_id):
    with connect() as conn:
        query = "SELECT count(*) FROM deliveries WHERE chat_id = ?"
        return conn.execute(query, (chat_id,)).fetchone()[0]


def test_seen_urls_are_personal():
    add_subscriber({}, 42)
    add_subscriber({}, 7)
    history.mark_as_sent(42, ["a", None, "a"])  # пустые url и повторы не пишем

    assert history.get_seen_urls(42) == {"a"}
    assert history.get_seen_urls(7) == set()  # у другого подписчика своя история
    assert _deliveries_count(42) == 1


def test_new_vacancies_skip_seen():
    df = pd.DataFrame({"url": ["a", "b", "c"]})

    assert list(history.get_new_vacancies_for_subscriber(df, {"a"})["url"]) == ["b", "c"]
    assert len(history.get_new_vacancies_for_subscriber(df, set())) == 3


def test_reset_hides_history_but_keeps_rows():
    add_subscriber({}, 42)
    history.mark_as_sent(42, ["a"])
    history.reset_subscriber_history(42)

    assert history.get_seen_urls(42) == set()  # после смены фильтров «а» снова новая
    history.mark_as_sent(42, ["a"])

    assert history.get_seen_urls(42) == {"a"}
    assert _deliveries_count(42) == 2  # обе отправки остались в журнале


def test_duplicate_urls_count_as_sent():
    df = pd.DataFrame({"url": ["a"], "duplicate_urls": [["b"]]})

    # раньше ушла версия с другого борда
    assert history.get_new_vacancies_for_subscriber(df, {"b"}).empty
    assert history.all_vacancy_urls(df) == ["a", "b"]
