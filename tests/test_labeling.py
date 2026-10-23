import pandas as pd

from eval.labeling import cohen_kappa, is_candidate, select_test
from pipeline.dedupe import _build_features


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


def test_is_candidate():
    urls = ["/vacancies/1-ds", "/vacancies/2-sr", "/vacancies/3-go", "/vacancies/1-data-scientist"]
    titles = ["data scientist", "senior data scientist (nlp)", "golang developer", "ml engineer"]
    df = pd.DataFrame({"url": urls, "company": "сбер", "title": titles, "description": None})
    f = _build_features(df, max_shingle_df=5)
    assert is_candidate(f[0], f[1])  # одно название внутри другого
    assert is_candidate(f[0], f[3])  # тот же id вакансии, сменился slug
    assert not is_candidate(f[0], f[2])
