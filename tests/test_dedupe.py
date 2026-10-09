import pandas as pd

from pipeline import dedupe
from pipeline.dedupe import _titles_match, deduplicate_vacancies

# куски описаний для тестов: настоящие вакансии длиннее, но принцип тот же
SCORING = (
    "разработка и поддержка моделей кредитного риска юридических лиц pd выручка и лимиты "
    "создание признаков и вывод их через feature store и онлайн каскады эксперименты "
    "с рекуррентными сетями на платежных данных поведенческая аналитика и сегментация"
)
RECSYS = (
    "написание сервисов для команды рекомендательных систем разработка систем мониторинга "
    "качества рекомендательных систем настройка мониторинга и алертинга качества данных "
    "написание юнит тестов на pytest и тестов для частей ml пайплайна участие в код ревью"
)
NLP = (
    "обучение языковых моделей для чат бота поддержки клиентов разметка диалогов оценка "
    "качества ответов дообучение llm на внутренних данных и сбор датасетов для классификации"
)
CV = (
    "детекция объектов на фотографиях документов распознавание текста ocr сегментация сканов "
    "обучение сверточных сетей и подготовка разметки для моделей компьютерного зрения"
)
CONDITIONS = "дмс с первого дня гибкий график оплата конференций и курсов корпоративная библиотека"


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


def test_cross_source_duplicates_by_full_title(make_vacancy):
    rows = [
        make_vacancy(url="a", company="сбер", title="data analyst", description="подробно"),
        make_vacancy(url="b", company="пао сбербанк", title="data analyst"),  # тот же сбер
        make_vacancy(url="c", company=None, title="data analyst"),  # компания скрыта — не склеиваем
        make_vacancy(url="d", company="ozon", title="data analyst"),  # другая компания
    ]
    result = deduplicate_vacancies(pd.DataFrame(rows)).set_index("url")

    assert sorted(result.index) == ["a", "c", "d"]
    assert result.loc["a", "duplicate_urls"] == ["b"]


# баг: группировали по сырой строке компании, и похожие тайтлы из «альфа банк»
# и «альфа-банк» не сравнивались между собой
def test_company_spelling_does_not_split_duplicates(make_vacancy):
    rows = [
        make_vacancy(url="a", company="альфа банк", title="data scientist", description="подробно"),
        make_vacancy(url="b", company="альфа-банк", title="data scientist (ai)"),
    ]
    result = deduplicate_vacancies(pd.DataFrame(rows))

    assert list(result["url"]) == ["a"] and result.loc[0, "duplicate_urls"] == ["b"]


def test_title_head_and_text_overlap():
    assert dedupe._title_head("senior ds в команду скоринга (юл)") == "senior ds"
    assert dedupe._title_head("ml-разработчик в розничные риски") == "ml-разработчик"
    # обрезанный текст целиком входит в полный, на пустом сравнивать нечего
    full, cut = dedupe._shingles(RECSYS), dedupe._shingles(" ".join(RECSYS.split()[:25]))
    assert dedupe._text_overlap(cut, full) == 1.0
    assert dedupe._text_overlap(frozenset(), full) is None


# кейсы со скринов рассылки: одну вакансию по-разному назвали на разных бордах
def test_reworded_titles_merged_by_description(make_vacancy):
    rows = [
        make_vacancy(url="hirify", company="альфа-банк", description=SCORING,
                     title="senior data scientist (кредитный скоринг юридических лиц)"),
        make_vacancy(url="getmatch", company="альфа-банк", description=f"{SCORING} {CONDITIONS}",
                     title="senior data scientist в команду скоринговых моделей юл"),
        make_vacancy(url="datasecrets", company="2gis", title="data scientist",
                     description=f"{RECSYS} {CONDITIONS}"),
        make_vacancy(url="hirify2", company="2gis", description=" ".join(RECSYS.split()[:30]),
                     title="data scientist (рекомендательные системы)"),  # hirify обрезает текст
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows)).set_index("url")

    expected = {"getmatch": ["hirify"], "datasecrets": ["hirify2"]}
    assert result["duplicate_urls"].to_dict() == expected


# похожие названия, но описания разные — это две вакансии, а не дубль.
# шаблон условий, общий для всех вакансий компании, схожести не добавляет
def test_similar_titles_with_different_texts_are_kept(make_vacancy):
    titles = ["data engineer", "аналитик данных", "backend разработчик", "devops", "продакт"]
    rows = [
        make_vacancy(url="nlp", company="сбер", title="data scientist (nlp)",
                     description=f"{NLP} {CONDITIONS}"),
        make_vacancy(url="cv", company="сбер", title="data scientist (cv)",
                     description=f"{CV} {CONDITIONS}"),
        *[make_vacancy(url=title, company="сбер", title=title, description=f"{title} {CONDITIONS}")
          for title in titles],
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows))

    assert sorted(result["url"]) == sorted(["nlp", "cv", *titles])


# без описаний переписанный тайтл не склеиваем: одной «головы» мало
def test_same_head_without_description_is_kept(make_vacancy):
    rows = [
        make_vacancy(url="a", company="2gis", title="data scientist"),
        make_vacancy(url="b", company="2gis", title="data scientist (рекомендательные системы)"),
    ]
    assert len(deduplicate_vacancies(pd.DataFrame(rows))) == 2
