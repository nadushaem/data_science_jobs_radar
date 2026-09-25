from pipeline.classify import classify_vacancy
from pipeline.keywords import EXCLUDED_ROLES, ROLE_TAXONOMY, TARGET_KEYWORDS


def _classify(vacancy):
    return classify_vacancy(vacancy, TARGET_KEYWORDS, ROLE_TAXONOMY, EXCLUDED_ROLES)


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
