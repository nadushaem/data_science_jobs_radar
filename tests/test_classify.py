from pipeline.classify import classify_vacancy
from pipeline.keywords import EXCLUDED_ROLES, INDUSTRY_EXCLUDES, ROLE_TAXONOMY, TARGET_KEYWORDS


def _classify(vacancy):
    return classify_vacancy(
        vacancy, TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES, INDUSTRY_EXCLUDES
    )


def test_target_vacancy(make_vacancy):
    result = _classify(make_vacancy(title="senior data scientist", description="финтех, python"))

    assert result["is_target"]
    assert result["fintech"] == ["финтех"]
    assert result["matched_roles"] == ["data_scientist"]


def test_no_industry_is_not_target(make_vacancy):
    result = _classify(make_vacancy(description="классический офлайн-ритейл"))
    assert not result["is_target"]


def test_excluded_role_is_not_target(make_vacancy):
    vacancy = make_vacancy(title="backend developer / data engineer", description="финтех")
    result = _classify(vacancy)

    assert result["matched_roles"] == ["data_engineer"]
    assert not result["is_target"]


def test_bigtech_is_it(make_vacancy):
    result = _classify(make_vacancy(company="яндекс", description="поиск и рекомендации"))

    assert result["it"] == ["яндекс"]
    assert result["is_target"]


def test_bigtech_subsidiary_is_not_it(make_vacancy):
    # «экосистема яндекса» в описании не должна вытягивать маркет в it
    vacancy = make_vacancy(company="яндекс маркет", description="экосистема яндекса, маркетплейс")
    result = _classify(vacancy)

    assert result["it"] == []
    assert result["ecommerce"]


def test_excluded_phrase_in_description_is_cut(make_vacancy):
    # упоминание партнёра вырезается, но сама компания остаётся в it
    vacancy = make_vacancy(company="yadro", description="интеграция с яндекс маркет")
    assert _classify(vacancy)["it"] == ["yadro"]
