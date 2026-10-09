import ast
import re
from difflib import SequenceMatcher

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


# компания без формы собственности, кавычек и разных дефисов: «ПАО «Сбер»» → «сбер»
def _company_key(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\b(ооо|ао|пао|зао|llc|ltd|inc)\b", " ", value.lower())
    return re.sub(r"[\W_]+", "", value)


# одна компания с разных бордов: «сбер» / «пао сбербанк». если компании нет хотя бы
# у одной версии — не склеиваем: при общих названиях это скорее разные вакансии
def _same_company(a, b):
    a, b = _company_key(a), _company_key(b)
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


# дубли из разных источников: полностью совпадающий title + совместимая компания.
# df отсортирован по полноте, поэтому первая встреченная версия — лучшая
def _drop_cross_source_duplicates(df, merged):
    keep, kept_by_title = [], {}

    for i in df.index:
        title, company = df.at[i, "title"], df.at[i, "company"]
        candidates = kept_by_title.get(title, [])
        same = [j for j in candidates if _same_company(df.at[j, "company"], company)]

        if isinstance(title, str) and same:
            merged.setdefault(same[0], []).extend([df.at[i, "url"], *merged.pop(i, [])])
        else:
            keep.append(i)
            kept_by_title.setdefault(title, []).append(i)

    return df.loc[keep]


# убираем дубли: точные по url, похожие по (company, title), затем одинаковые title
# с разных бордов. url выкинутых дублей сохраняем в duplicate_urls — их учитывает история рассылок
def deduplicate_vacancies(df, title_similarity_threshold=0.85):
    df = df.copy()

    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)

    df["_completeness"] = df.apply(_completeness_score, axis=1)
    df = df.sort_values("_completeness", ascending=False).reset_index(drop=True)

    keep_indices = []
    used = set()
    merged = {}  # индекс оставленной вакансии → url её дублей

    companies = df["company"] if "company" in df.columns else pd.Series(pd.NA, index=df.index)
    company_keys = companies.map(_company_key)
    group_key = company_keys.where(company_keys != "", "__no_company_" + df.index.astype(str))
    for _, group in df.groupby(group_key):
        indices = group.index.tolist()

        for i in indices:
            if i in used:
                continue

            keep_indices.append(i)
            used.add(i)
            title_i = df.loc[i, "title"]

            for j in indices:
                if j in used:
                    continue

                if _titles_match(title_i, df.loc[j, "title"], title_similarity_threshold):
                    used.add(j)
                    merged.setdefault(i, []).append(df.loc[j, "url"])

    df = _drop_cross_source_duplicates(df.loc[sorted(keep_indices)], merged)
    df["duplicate_urls"] = [merged.get(i, []) for i in df.index]

    return df.drop(columns=["_completeness"]).reset_index(drop=True)
