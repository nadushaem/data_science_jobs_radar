import pandas as pd

from pipeline.dedupe import _titles_match, deduplicate_vacancies


def test_titles_match():
    assert _titles_match("senior data scientist", "senior data scientist (ml)", 0.85)
    assert not _titles_match("data scientist", "data engineer", 0.85)
    assert not _titles_match(None, "data scientist", 0.85)


def test_deduplicate_keeps_most_complete_version(make_vacancy):
    rows = [
        make_vacancy(url="a", description="коротко"),
        make_vacancy(url="b", description="подробное описание", salary_min=200_000),
        make_vacancy(url="a", description="коротко"),  # точный дубль по url
        make_vacancy(url="c", company="other"),  # та же роль в другой компании
        make_vacancy(url="d", company=None),  # без компании не склеиваем
        make_vacancy(url="e", company=None),
    ]
    result = deduplicate_vacancies(pd.DataFrame(rows))

    assert sorted(result["url"]) == ["b", "c", "d", "e"]
