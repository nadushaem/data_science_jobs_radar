import pandas as pd

from keywords import INDUSTRY_LABELS


def _industries_title(industries):
    if not industries:
        return "все сферы"
    return ", ".join(INDUSTRY_LABELS.get(key, key) for key in industries)


# вакансия попадает под фильтр, если хотя бы в одной из выбранных сфер
# нашлись ключевые слова (см. classify.py — там vacancy[category] = список слов)
def _industry_mask(df, industries):
    columns = [key for key in industries if key in df.columns]

    if not columns:
        return pd.Series(True, index=df.index)

    return df[columns].apply(lambda col: col.map(bool)).any(axis=1)


# отдельная функция, чтобы фильтровать df один раз и переиспользовать
# результат и для отправки, и для пометки "отправлено" в истории
def filter_by_industries(df, industries):
    if "is_target" in df.columns:
        df = df[df["is_target"]]

    if industries:
        df = df[_industry_mask(df, industries)]

    return df


def _capitalize_first(text):
    if not text:
        return text
    return text[0].upper() + text[1:]


# грейд может быть списком (["Миддл"]), строкой или None —
# приводим к читаемому виду, если пусто — явно пишем "не указан"
def _format_level(value):
    if isinstance(value, list) and value:
        return ", ".join(value)
    if isinstance(value, str) and value:
        return value
    return "не указан"


# форматируем одну вакансию: должность, компания, грейд, ссылка
def _format_vacancy(row, index):
    title = _capitalize_first(row.get("title")) or "—"
    lines = [f"{index}. *{title}*"]

    company = _capitalize_first(row.get("company"))
    if company:
        lines.append(f"🏢 {company}")

    lines.append(f"🎯 Грейд: {_format_level(row.get('level'))}")

    if row.get("url"):
        lines.append(row["url"])

    return "\n".join(lines)


# ВАЖНО: df на входе уже должен быть отфильтрован по сферам
# (см. filter_by_industries) — здесь мы только собираем текст сообщений
def build_summary_messages(df, is_new_subscriber=False, industries=None,
                            days=7, max_length=3500):
    scope = _industries_title(industries)

    if is_new_subscriber:
        intro = f"📅 Вакансии за последние {days} дней ({len(df)}) — {scope}"
    else:
        intro = f"🆕 Новые вакансии ({len(df)}) — {scope}"

    items = [
        _format_vacancy(row, i + 1)
        for i, row in enumerate(df.to_dict("records"))
    ]

    # разбиваем на сообщения по max_length, не разрывая вакансию пополам
    messages = []
    current = intro

    for item in items:
        candidate = f"{current}\n\n{item}"

        if len(candidate) > max_length:
            messages.append(current)
            current = item
        else:
            current = candidate

    messages.append(current)
    return messages