import ast

import pandas as pd
from difflib import SequenceMatcher


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

    if shorter and shorter in longer:
        if len(shorter) / len(longer) >= min_length_ratio:
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


# убираем дубли: сначала точные по url, потом похожие по (company, title)
def deduplicate_vacancies(df, title_similarity_threshold=0.85):
    df = df.copy()

    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)

    df["_completeness"] = df.apply(_completeness_score, axis=1)
    df = df.sort_values("_completeness", ascending=False).reset_index(drop=True)

    keep_indices = []
    used = set()

    # безымянные company не группируем вместе — у каждой своя "группа из одного"
    has_company = df["company"].notna() if "company" in df.columns else pd.Series([False] * len(df))
    group_key = df["company"].where(has_company, df.index.to_series().map(lambda i: f"__no_company_{i}"))

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

                title_j = df.loc[j, "title"]

                if _titles_match(title_i, title_j, title_similarity_threshold):
                    used.add(j)

    result = df.loc[sorted(keep_indices)].drop(columns=["_completeness"]).reset_index(drop=True)
    return result