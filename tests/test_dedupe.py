import pandas as pd

from pipeline.dedupe import _company_key, _title_words, _titles_compatible, deduplicate_vacancies

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


def test_company_key():
    assert _company_key("Aльфа-Банк") == _company_key("Альфа банк")  # латинская «A»
    assert _company_key("2ГИС") == _company_key("2GIS")
    assert _company_key("Яндекс") == _company_key("Yandex")
    # заглушки вместо компании — как будто компании нет
    assert _company_key("Компания скрыта (банк)") == _company_key("NDA") == ""
    assert _company_key("Ndata") == "ndata"


def test_titles_compatible():
    def compatible(a, b):
        return _titles_compatible(_title_words(a), _title_words(b))

    assert compatible("data scientist", "Data Scientist (fintech)")
    assert compatible("старший аналитик", "senior аналитик (sql)")
    assert compatible("senior devops", "devops senior")
    assert not compatible("data scientist (nlp)", "data scientist (cv)")
    assert not compatible("junior qa", "senior qa")
    assert not compatible("senior go developer", "senior python developer")
    assert not compatible(None, "data scientist")


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
        make_vacancy(url="a", source="getmatch", company="сбер", title="data analyst",
                     description="подробно"),
        make_vacancy(url="b", source="hirify", company="пао сбербанк", title="data analyst"),
        make_vacancy(url="c", company=None, title="data analyst"),  # компания скрыта
        make_vacancy(url="d", company="ozon", title="data analyst"),  # другая компания
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows)).set_index("url")

    assert sorted(result.index) == ["a", "c", "d"]
    assert result.loc["a", "duplicate_urls"] == ["b"]


# hirify дописывает отрасль в скобках и пересказывает описание — это всё равно дубль
def test_cross_board_versions_are_merged(make_vacancy):
    rows = [
        make_vacancy(url="g1", source="getmatch", company="альфа банк", title="data scientist",
                     description="подробно"),
        make_vacancy(url="h1", source="hirify", company="альфа-банк", title="data scientist (ai)"),
        make_vacancy(url="g2", source="getmatch", company="мегафон",
                     title="python разработчик (middle)", description=NLP),
        make_vacancy(url="h2", source="hirify", company="мегафон",
                     title="python разработчик (middle)", description=CV),
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows)).set_index("url")

    assert result["duplicate_urls"].to_dict() == {"g1": ["h1"], "g2": ["h2"]}


# с разметки: у отп три «middle support engineer» на getmatch — три разные команды.
# на одном борде одинаковое название без общего текста — не дубль, а повтор текста — дубль
def test_same_board_needs_shared_text(make_vacancy):
    rows = [
        make_vacancy(url=f"otp{i}", source="getmatch", company="отп банк",
                     title="middle support engineer", description=text)
        for i, text in enumerate([NLP, SCORING, RECSYS])
    ]  # fmt: skip
    rows += [
        make_vacancy(url="a", source="hirify", company="centicore",
                     title="senior python developer (llm)", description=f"{CV} {NLP}"),
        make_vacancy(url="b", source="hirify", company="centicore",
                     title="senior python developer (llm)", description=f"{CV} {NLP}"),
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows))

    assert sorted(result["url"]) == ["a", "otp0", "otp1", "otp2"]


# «data scientist» с datasecrets совместим с обеими вакансиями hirify, но склеиться
# должен с той, где общий текст. сами вакансии hirify разные, поэтому в одну группу
# все три не попадают, даже если первой обработать самую полную — скоринг
def test_bare_title_joins_most_similar_version(make_vacancy):
    rows = [
        make_vacancy(url="scoring", source="hirify", company="альфа-банк", salary_min=300_000,
                     title="senior data scientist (кредитный скоринг)"),
        make_vacancy(url="ds", source="datasecrets", company="альфа-банк", title="data scientist",
                     description=RECSYS),
        make_vacancy(url="ai", source="hirify", company="альфа-банк", title="data scientist (ai)",
                     description=" ".join(RECSYS.split()[:30])),
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows)).set_index("url")

    assert result["duplicate_urls"].to_dict() == {"scoring": [], "ds": ["ai"]}


# один id на getmatch, но slug сменился вместе с названием; и переписанное название
# с тем же текстом на другом борде («менеджер по продажам» / «sales-менеджер»)
def test_same_id_and_shared_text_are_merged(make_vacancy):
    rows = [
        make_vacancy(url="https://getmatch.ru/vacancies/36670-1s-zup-ooo", source="getmatch",
                     company="рсхб-интех", title='руководитель 1с зуп (ооо "рсхб-интех")',
                     description="подробно"),
        make_vacancy(url="https://getmatch.ru/vacancies/36670-1s-zup", source="getmatch",
                     company="рсхб-интех", title="руководитель 1с зуп"),
        make_vacancy(url="geekjob", source="geekjob", company="soft media group",
                     title="менеджер по продажам в it-компанию", description=f"{RECSYS} {NLP}"),
        make_vacancy(url="hirify", source="hirify", company="soft media group",
                     title="sales-менеджер (it/cms)", description=RECSYS),
    ]  # fmt: skip
    result = deduplicate_vacancies(pd.DataFrame(rows))

    assert len(result) == 2
