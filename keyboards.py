from keywords import INDUSTRY_LABELS, ROLE_LABELS

INDUSTRIES_BUTTON_TEXT = "🎯 Выбрать сферы"
ROLES_BUTTON_TEXT = "🧩 Выбрать роли"
TOP_SKILLS_BUTTON_TEXT = "📊 Топ навыков"
VIEW_ALL_BUTTON_TEXT = "👀 Посмотреть вакансии"
UNSUBSCRIBE_BUTTON_TEXT = "🚫 Отказаться от рассылки"


def industries_text(industries):
    if not industries:
        return "сейчас: все сферы"
    labels = [INDUSTRY_LABELS.get(key, key) for key in industries]
    return "сейчас: " + ", ".join(labels)


def roles_text(roles):
    if not roles:
        return "сейчас: все роли"
    labels = [ROLE_LABELS.get(key, key) for key in roles]
    return "сейчас: " + ", ".join(labels)


# общий конструктор клавиатуры выбора из словаря {key: label} —
# используется и для сфер, и для ролей, чтобы не дублировать раскладку
def _build_choice_keyboard(labels, selected, toggle_prefix, reset_data, confirm_data):
    selected = set(selected or [])
    rows = []
    row = []

    for key, label in labels.items():
        mark = "✅ " if key in selected else "▫️ "
        row.append({"text": mark + label, "callback_data": f"{toggle_prefix}:{key}"})

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([{"text": "♻️ Сбросить", "callback_data": reset_data}])
    rows.append([{"text": "✅ Показать вакансии", "callback_data": confirm_data}])

    return {"inline_keyboard": rows}


def build_industries_keyboard(selected):
    return _build_choice_keyboard(
        INDUSTRY_LABELS, selected, "ind_toggle", "ind_reset", "ind_confirm",
    )


def build_roles_keyboard(selected):
    return _build_choice_keyboard(
        ROLE_LABELS, selected, "role_toggle", "role_reset", "role_confirm",
    )


def build_main_keyboard():
    return {
        "keyboard": [
            [{"text": INDUSTRIES_BUTTON_TEXT}, {"text": ROLES_BUTTON_TEXT}],
            [{"text": TOP_SKILLS_BUTTON_TEXT}, {"text": VIEW_ALL_BUTTON_TEXT}],
            [{"text": UNSUBSCRIBE_BUTTON_TEXT}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }