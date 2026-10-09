import ast
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import partial

import pandas as pd


# CSV не хранит типы-списки (skills, specialization, ...) после
# pd.read_csv превращаются в строку "['python', 'sql']". Восстанавливаем
# обратно в list, чтобы _completeness_score считал их корректно
def _parse_list_cell(value):
    if isinstance(value, list):
        return value

    if pd.isna(value):
        return None

    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value

    return parsed if isinstance(parsed, list) else value


# насколько похожи два заголовка (0..1) + отдельно проверяем вхождение
# подстроки (частый кейс: один источник добавляет уточнение в скобках).
# вхождение считаем дублем, только если короткий тайтл — заметная часть длинного
def _titles_match(a, b, threshold, min_length_ratio=0.7):
    if not a or not b:
        return False

    a, b = str(a), str(b)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)

    if shorter and shorter in longer and len(shorter) / len(longer) >= min_length_ratio:
        return True

    return SequenceMatcher(None, a, b).ratio() >= threshold


# оцениваем "полноту" вакансии — чтобы при дубле оставить лучшую версию
def _completeness_score(row):
    score = 0

    if pd.notna(row.get("salary_min")):
        score += 1
    if pd.notna(row.get("salary_max")):
        score += 1

    description = row.get("description")
    if isinstance(description, str):
        score += len(description) / 1000

    skills = row.get("skills")
    if isinstance(skills, list):
        score += len(skills)

    return score


# заглушки вместо названия компании (уже в виде _company_key) — считаем, что компании нет
HIDDEN_COMPANIES = {"companyhidden"}


# компания без формы собственности, кавычек и разных дефисов: «ПАО «Сбер»» → «сбер»
def _company_key(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\b(ооо|ао|пао|зао|llc|ltd|inc)\b", " ", value.lower())
    key = re.sub(r"[\W_]+", "", value)
    return "" if key in HIDDEN_COMPANIES else key


# одна компания с разных бордов: «сбер» / «пао сбербанк». если компании нет хотя бы
# у одной версии — не склеиваем: при общих названиях это скорее разные вакансии.
# принимает уже посчитанные _company_key
def _same_company(a, b):
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


# «голова» тайтла без уточнений, дефисы как пробелы:
# «senior ds в команду скоринга (юл)» → «senior ds», «продакт-менеджер (b2c)» → «продакт менеджер»
def _title_head(title):
    if not isinstance(title, str):
        return ""
    head = re.split(r"\s*[(,]|\s+(?:в|для|на)\s+|\s+[-–—/|]\s+", title, maxsplit=1)[0]
    return re.sub(r"[\s\-–—]+", " ", head).strip()


# описание → множество триграмм слов. по ним сравниваем тексты с разных бордов
def _shingles(text, size=3):
    if not isinstance(text, str):
        return frozenset()
    words = re.findall(r"\w+", text.lower())
    return frozenset(zip(*(words[i:] for i in range(size)), strict=False))


# какая доля короткого текста есть в длинном (0..1). делим на меньший, а не на объединение:
# hirify отдаёт обрезанное описание, и оно целиком «входит» в полное с другого борда.
# на слишком коротких текстах оценка шумная — возвращаем None, «текста нет»
def _text_overlap(a, b, min_shingles=20):
    if min(len(a), len(b)) < min_shingles:
        return None
    return len(a & b) / min(len(a), len(b))


# признаки для сравнения пар — по словарю на строку df, считаем один раз на вакансию.
# шаблонный текст («дмс с первого дня», «знание python и sql») есть во многих описаниях
# и делает похожими разные вакансии. одна вакансия висит максимум на нескольких бордах,
# поэтому триграммы чаще чем в max_shingle_df описаниях не учитываем — как max_df в tf-idf
def _build_features(df, max_shingle_df):
    features = [
        {
            "url": row.get("url"), "company": _company_key(row.get("company")),
            "title": row.get("title"), "head": _title_head(row.get("title")),
            "shingles": _shingles(row.get("description")),
        }
        for row in df.to_dict("records")
    ]  # fmt: skip

    counts = Counter(shingle for feature in features for shingle in feature["shingles"])
    common = {shingle for shingle, count in counts.items() if count > max_shingle_df}
    for feature in features:
        feature["shingles"] -= common
    return features


# решаем, дубль ли пара вакансий одной компании:
# - похожие тайтлы: дубль, если описания нечем сравнить или у них есть общий текст.
#   иначе это разные вакансии с похожими названиями: «data scientist (nlp)» / «(cv)»
# - тайтлы переписаны, но «голова» та же: дубль, только если описание в основном общее
def _is_duplicate(a, b, title_threshold, text_threshold, min_text_overlap):
    overlap = _text_overlap(a["shingles"], b["shingles"])

    if _titles_match(a["title"], b["title"], title_threshold):
        return overlap is None or overlap >= min_text_overlap

    # головы сравниваем строго: «руководитель ai-отдела» и «руководитель 3d-отдела» похожи на 0.91
    heads_match = bool(a["head"]) and a["head"] == b["head"]
    return heads_match and overlap is not None and overlap >= text_threshold


# убираем дубли: точные по url, затем одна вакансия с разных бордов (см. _is_duplicate).
# url выкинутых дублей сохраняем в duplicate_urls — их учитывает история рассылок
def deduplicate_vacancies(
    df, title_similarity_threshold=0.85, text_overlap_threshold=0.4, min_text_overlap=0.2,
    max_shingle_df=5,
):  # fmt: skip
    df = df.copy()

    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)

    # сначала самые полные версии: из группы дублей остаётся первая встреченная
    df["_completeness"] = df.apply(_completeness_score, axis=1)
    df = df.sort_values("_completeness", ascending=False, kind="stable").reset_index(drop=True)

    features = _build_features(df, max_shingle_df)
    is_duplicate = partial(
        _is_duplicate, title_threshold=title_similarity_threshold,
        text_threshold=text_overlap_threshold, min_text_overlap=min_text_overlap,
    )  # fmt: skip
    kept, kept_by_company = [], {}  # оставленные индексы и они же по ключу компании
    merged = {}  # индекс оставленной вакансии → url её дублей

    for i, current in enumerate(features):
        company = current["company"]
        candidates = [
            j for key, indices in kept_by_company.items() if _same_company(key, company)
            for j in indices
        ]  # fmt: skip
        # из подходящих берём самую полную версию — у неё наименьший индекс
        matches = [j for j in candidates if is_duplicate(features[j], current)]
        duplicate_of = min(matches, default=None)

        if duplicate_of is None:
            kept.append(i)
            # без компании в кандидаты не попадаем — такие вакансии не склеиваем
            if company:
                kept_by_company.setdefault(company, []).append(i)
        else:
            merged.setdefault(duplicate_of, []).append(current["url"])

    df = df.loc[kept]
    df["duplicate_urls"] = [merged.get(i, []) for i in df.index]

    return df.drop(columns=["_completeness"]).reset_index(drop=True)
