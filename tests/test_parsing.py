import pytest

from pipeline import parsing
from pipeline.keywords import EXCLUDED_ROLES, LEVEL_TAXONOMY, ROLE_TAXONOMY


def test_find_keywords_is_case_insensitive():
    assert parsing.find_keywords("Мы — ФИНТЕХ", ["финтех", "fintech"]) == ["финтех"]
    assert parsing.find_keywords(None, ["финтех"]) == []


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Data Scientist", ["data_scientist"]),
        ("ML - инженер", ["ml_engineer"]),
        ("Data Analyst", ["data_analyst"]),
        ("HTML Engineer", []),  # "ml engineer" внутри слова не считается
        ("Deep Learning Engineer", ["dl_engineer"]),
        ("Senior DL - инженер", ["dl_engineer"]),
        ("Frontend Developer", []),
        ("AI Engineer", ["ai_engineer"]),
        ("LLM-инженер", ["ai_engineer"]),
        ("Разработчик AI-агентов", ["ai_engineer"]),
        (None, []),
    ],
)
def test_find_roles(title, expected):
    assert parsing.find_roles(title, ROLE_TAXONOMY) == expected


def test_find_roles_ai_with_spaces():
    assert "ai_engineer" in parsing.find_roles("AI / ML Engineer", ROLE_TAXONOMY)


def test_excluded_roles_match_whole_words():
    assert parsing.find_excluded_roles("iOS-разработчик", EXCLUDED_ROLES) == ["ios"]
    # "ios" внутри "portfolios" — не повод выкидывать вакансию
    title = "Data Scientist (Credit Portfolios)"
    assert parsing.find_excluded_roles(title, EXCLUDED_ROLES) == []
    assert parsing.find_excluded_roles("Content Manager (AI/ML)", EXCLUDED_ROLES) == [
        "content manager"
    ]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Data Scientist", ["Сеньор"]),
        ("Team Lead ML", ["Тимлид/Руководитель группы"]),
        ("Head of Data", ["Руководитель отдела/подразделения"]),
        ("Lead Generation Manager", None),  # "lead" здесь не про грейд
        ("Data Scientist", None),
    ],
)
def test_guess_level(title, expected):
    assert parsing.guess_level(title, LEVEL_TAXONOMY) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("от 200 000 ₽", (200_000, None, "RUB", "month")),
        ("100 000 – 150 000 руб.", (100_000, 150_000, "RUB", "month")),
        ("до 5000 $", (None, 5000, "USD", "month")),
        ("$5k", (5000, None, "USD", "month")),
        ("3 600 000 ₽ в год", (3_600_000, None, "RUB", "year")),
        (None, (None, None, None, "month")),
    ],
)
def test_parse_salary(raw, expected):
    result = parsing.parse_salary(raw)
    keys = ("salary_min", "salary_max", "currency", "salary_period")
    assert tuple(result[key] for key in keys) == expected


def test_strip_html():
    assert parsing.strip_html("<p>Финтех <b>стартап</b></p>") == "Финтех стартап"
    assert parsing.strip_html(None) is None


def test_get_search_text_flattens_lists():
    vacancy = {"title": "ds", "description": None, "skills": ["python", "sql"]}
    assert parsing.get_search_text(vacancy) == "ds python sql"
