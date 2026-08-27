import pandas as pd


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
    lines = [f"{index}. *{row.get('title') or '—'}*"]

    company = row.get("company")
    if company:
        lines.append(f"🏢 {company}")

    lines.append(f"🎯 Грейд: {_format_level(row.get('level'))}")

    if row.get("url"):
        lines.append(row["url"])

    return "\n".join(lines)


# собираем список сообщений (список, а не секции — recsys/медицина больше не делим)
def build_summary_messages(df, days=7, max_length=3500):
    df = df[df["is_target"]]

    intro = f"📅 Сводка вакансий за последние {days} дней ({len(df)})"

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