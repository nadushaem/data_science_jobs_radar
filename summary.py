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


# собираем список сообщений
def build_summary_messages(target_df, is_new_subscriber, days=7, max_length=3500):
    if is_new_subscriber:
        intro = f"📅 Сводка вакансий за последние {days} дней ({len(target_df)})"
    else:
        intro = f"📅 Есть новые вакансии! ({len(target_df)})"

    items = [
        _format_vacancy(row, i + 1)
        for i, row in enumerate(target_df.to_dict("records"))
    ]

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