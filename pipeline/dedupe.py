import ast
import re
from collections import Counter
from itertools import combinations, product

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


# заглушки вместо названия компании (уже в виде ключа) — считаем, что компании нет.
# «компания скрыта (банк)» → «kompaniyaskrytabank», поэтому у неё проверяем начало
HIDDEN_COMPANY = re.compile(r"nda|companyhidden|kompaniyaskryta\w*")
# кириллица → латиница: «2гис» / «2gis», «яндекс» / «yandex», «aльфа» с латинской «a»
TRANSLIT = str.maketrans(
    dict(zip("абвгдеёзийклмнопрстуфхцыэ", "abvgdeeziiklmnoprstufhcye", strict=True))
    | {"ж": "zh", "ч": "ch", "ш": "sh", "щ": "sch", "ю": "yu", "я": "ya", "ъ": "", "ь": ""}
)


# компания без формы собственности и знаков, в латинице: «ПАО «Сбер»» → «sber»
def _company_key(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\b(ооо|ао|пао|зао|llc|ltd|inc)\b", " ", value.lower())
    key = re.sub(r"[\W_]+", "", value).translate(TRANSLIT).replace("ks", "x")
    return "" if HIDDEN_COMPANY.fullmatch(key) else key


# одна компания с разных бордов: «sber» / «sberbank». принимает уже посчитанные ключи;
# если компании нет хотя бы у одной версии — не склеиваем
def _same_company(a, b):
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


# url без slug: getmatch меняет slug при смене названия, а id вакансии остаётся тем же
def _url_key(url):
    return re.sub(r"(/(?:vacancies|jobs)/\d+)-[^/?#]*", r"\1", str(url))


TITLE_SYNONYMS = {
    "старший": "senior", "сеньор": "senior", "sr": "senior", "младший": "junior",
    "jr": "junior", "мидл": "middle", "финтех": "fintech", "ии": "ai", "ит": "it",
}  # fmt: skip
TITLE_STOP_WORDS = {"в", "во", "для", "на", "по", "и", "с", "команду", "группу"}


# название → множество слов: синонимы грейдов и отраслей, без предлогов
def _title_words(title):
    if not isinstance(title, str):
        return frozenset()
    words = re.findall(r"[a-zа-я0-9+#]+", title.lower().replace("ё", "е"))
    words = (TITLE_SYNONYMS.get(word, word) for word in words)
    return frozenset(word for word in words if word not in TITLE_STOP_WORDS)


# «голова» названия без уточнений: «senior ds в команду скоринга (юл)» → «senior ds»
def _title_head(title):
    if not isinstance(title, str):
        return frozenset()
    head = re.split(r"\s*[(,]|\s+(?:в|для|на)\s+|\s+[-–—/|]\s+", title, maxsplit=1)[0]
    return _title_words(head)


# названия совместимы, если слова одного входят в другое: борд дописал уточнение
# или грейд — «data scientist» / «data scientist (fintech)». разные уточнения
# с обеих сторон («(nlp)» / «(cv)»), разные грейды или стек — несовместимы
def _titles_compatible(a, b):
    return bool(a and b) and (a <= b or b <= a)


# описание → множество триграмм слов
def _shingles(text, size=3):
    if not isinstance(text, str):
        return frozenset()
    words = re.findall(r"\w+", text.lower())
    return frozenset(zip(*(words[i:] for i in range(size)), strict=False))


# какая доля короткого текста есть в длинном (0..1). на коротких текстах оценка шумная —
# возвращаем None, «текста нет»
def _text_overlap(a, b, min_shingles=20):
    if min(len(a), len(b)) < min_shingles:
        return None
    return len(a & b) / min(len(a), len(b))


# признаки для сравнения пар, один раз на вакансию. шаблонный текст («дмс с первого
# дня», «знание python и sql») делает похожими разные вакансии, поэтому триграммы,
# которые есть больше чем в max_shingle_df описаниях снапшота, не учитываем — как max_df в tf-idf
def _build_features(df, max_shingle_df):
    features = [
        {
            "url": row.get("url"), "url_key": _url_key(row.get("url")),
            "source": row.get("source"), "company": _company_key(row.get("company")),
            "words": _title_words(row.get("title")), "head": _title_head(row.get("title")),
            "shingles": _shingles(row.get("description")),
        }
        for row in df.to_dict("records")
    ]  # fmt: skip

    counts = Counter(shingle for feature in features for shingle in feature["shingles"])
    common = {shingle for shingle, count in counts.items() if count > max_shingle_df}
    for feature in features:
        feature["shingles"] -= common
    return features


# дубль ли пара вакансий одной компании. правило подобрано по разметке eval/dedupe_gold_v1
def _is_duplicate(a, b, cross_text, text_only, same_board_text):
    if a["url_key"] == b["url_key"]:
        return True

    overlap = _text_overlap(a["shingles"], b["shingles"])
    has_text = overlap is not None
    compatible = _titles_compatible(a["words"], b["words"])

    if a["source"] != b["source"]:
        if a["words"] and a["words"] == b["words"]:
            return True
        if not has_text:
            return compatible
        same_head = bool(a["head"]) and a["head"] == b["head"]
        return (compatible or same_head) and overlap >= cross_text or overlap >= text_only

    if not has_text:
        return bool(a["words"]) and a["words"] == b["words"]
    return compatible and overlap >= same_board_text


# пары-кандидаты: вакансии совместимых компаний. без компании вакансию не склеиваем
def _company_pairs(features):
    by_company = {}
    for i, feature in enumerate(features):
        if feature["company"]:
            by_company.setdefault(feature["company"], []).append(i)

    keys = list(by_company)
    for x, key in enumerate(keys):
        yield from combinations(by_company[key], 2)
        for other in keys[x + 1 :]:
            if _same_company(key, other):
                yield from product(by_company[key], by_company[other])


# насколько похожа пара: общий текст, затем доля общих слов в названиях
def _similarity(a, b):
    overlap = _text_overlap(a["shingles"], b["shingles"]) or 0
    return overlap, len(a["words"] & b["words"]) / (len(a["words"] | b["words"]) or 1)


# убираем дубли: точные по url, затем разные версии одной вакансии (см. _is_duplicate).
# url выкинутых дублей сохраняем в duplicate_urls — их учитывает история рассылок
def deduplicate_vacancies(
    df, cross_text=0.1, text_only=0.5, same_board_text=0.3, max_shingle_df=5
):  # fmt: skip
    df = df.copy()

    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)

    # сначала самые полные версии: в группе дублей остаётся вакансия с наименьшим индексом
    df["_completeness"] = df.apply(_completeness_score, axis=1)
    df = df.sort_values("_completeness", ascending=False, kind="stable").reset_index(drop=True)

    features = _build_features(df, max_shingle_df)
    thresholds = dict(cross_text=cross_text, text_only=text_only, same_board_text=same_board_text)
    pairs = [
        (i, j) for i, j in _company_pairs(features)
        if _is_duplicate(features[i], features[j], **thresholds)
    ]  # fmt: skip
    duplicates = set(pairs) | {(j, i) for i, j in pairs}

    # собираем группы, начиная с самых похожих пар. группы сливаем, только если каждая
    # вакансия одной — дубль каждой вакансии другой. иначе «data scientist» склеит
    # в одну группу «(nlp)» и «(cv)», а порядок обхода решит, куда он попадёт
    pairs.sort(key=lambda pair: _similarity(features[pair[0]], features[pair[1]]), reverse=True)
    group_of = {i: [i] for i in range(len(features))}
    for i, j in pairs:
        a, b = group_of[i], group_of[j]
        if a is not b and all((m, k) in duplicates for m in a for k in b):
            a += b
            group_of.update(dict.fromkeys(b, a))

    groups = {min(group): sorted(group) for group in group_of.values()}
    df = df.loc[sorted(groups)]
    df["duplicate_urls"] = [[features[m]["url"] for m in groups[i][1:]] for i in df.index]

    return df.drop(columns=["_completeness"]).reset_index(drop=True)
