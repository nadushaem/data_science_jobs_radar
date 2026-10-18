import pandas as pd

from eval.labeling import cohen_kappa, select_test


def _df(rows):
    return pd.DataFrame(rows, columns=["url", "company", "title"])


def test_select_test_drops_dev_overlap_and_reposts():
    dev = _df([("u1", "Сбер", "Data Scientist")])
    raw = _df([
        ("u1", "Сбер", "Data Scientist"),  # тот же url, что в dev
        ("u2", "ПАО Сбер", "Data  scientist"),  # перепост вакансии из dev
        ("u3", "Яндекс", "ML Engineer"),
        ("u4", "Yandex", "ml engineer"),  # перепост внутри недели
        ("u5", None, "Data Analyst"),
        ("u6", None, "Data Analyst"),  # без компании не склеиваем
    ])  # fmt: skip
    assert select_test(raw, dev)["url"].tolist() == ["u3", "u5", "u6"]


def test_cohen_kappa():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == 0
