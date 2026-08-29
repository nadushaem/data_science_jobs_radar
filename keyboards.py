from keywords import INDUSTRY_LABELS

INDUSTRIES_BUTTON_TEXT = "🎯 Выбрать сферы"


def industries_text(industries):
    if not industries:
        return "сейчас: все сферы"

    labels = [INDUSTRY_LABELS.get(key, key) for key in industries]
    return "сейчас: " + ", ".join(labels)


# инлайн-клавиатура выбора сфер — прикрепляется к сообщению /industries
def build_industries_keyboard(selected):
    selected = set(selected or [])
    rows = []
    row = []

    for key, label in INDUSTRY_LABELS.items():
        mark = "✅ " if key in selected else "▫️ "
        row.append({"text": mark + label, "callback_data": f"ind_toggle:{key}"})

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([{
        "text": "♻️ Сбросить (показывать все сферы)",
        "callback_data": "ind_reset",
    }])
    rows.append([{
        "text": "✅ Показать вакансии",
        "callback_data": "ind_confirm",
    }])

    return {"inline_keyboard": rows}


# постоянная клавиатура под полем ввода
def build_main_keyboard():
    return {
        "keyboard": [[{"text": INDUSTRIES_BUTTON_TEXT}]],
        "resize_keyboard": True,
        "is_persistent": True,
    }