import os
import time
import pandas as pd

from telegram_api import (
    get_updates, send_message, edit_message_reply_markup, answer_callback_query,
)
from subscribers import (
    load_subscribers, save_subscribers,
    get_industries, set_industries, get_roles, set_roles,
)
from keyboards import (
    build_industries_keyboard, build_roles_keyboard, build_main_keyboard,
    industries_text, roles_text, INDUSTRIES_BUTTON_TEXT,
    ROLES_BUTTON_TEXT, TOP_SKILLS_BUTTON_TEXT, VIEW_ALL_BUTTON_TEXT,
    UNSUBSCRIBE_BUTTON_TEXT,
)
from history import (
    load_sent_vacancies, save_sent_vacancies, prune_sent_vacancies,
    get_new_vacancies_for_subscriber, mark_as_sent, reset_subscriber_history,
)
from summary import build_summary_messages, filter_vacancies
from stats import build_top_skills_message


OFFSET_FILE = "data/telegram_offset.txt"
LATEST_VACANCIES_FILE = "data/vacancies_latest.pkl"


# описание одного фильтра: как читать/писать выбор, строить клавиатуру
# и текст меню. добавление нового фильтра (например, грейд) — это
# просто ещё одна запись в этом словаре, без новых if/elif по коду
_FILTERS = {
    "ind": {
        "get": get_industries, "set": set_industries,
        "keyboard": build_industries_keyboard, "text": industries_text,
        "menu_title": "Выберите сферы, вакансии из которых хотите видеть",
    },
    "role": {
        "get": get_roles, "set": set_roles,
        "keyboard": build_roles_keyboard, "text": roles_text,
        "menu_title": "Выберите роли, вакансии на которые хотите видеть",
    },
}


def _load_offset():
    if not os.path.exists(OFFSET_FILE):
        return 0
    with open(OFFSET_FILE, "r", encoding="utf-8") as file:
        return int(file.read().strip() or 0)


def _save_offset(offset):
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, "w", encoding="utf-8") as file:
        file.write(str(offset))


# общий (не персональный!) снэпшот вакансий последнего run() из main.py
def _load_latest_vacancies():
    if not os.path.exists(LATEST_VACANCIES_FILE):
        return pd.DataFrame()
    return pd.read_pickle(LATEST_VACANCIES_FILE)


# === доставка вакансий одному подписчику ===

def _deliver_vacancies(chat_id, industries, roles, target_df, sent):
    candidates = get_new_vacancies_for_subscriber(target_df, sent, chat_id)
    candidates = filter_vacancies(candidates, industries=industries, roles=roles)

    if candidates.empty:
        return sent, False

    is_new_subscriber = str(chat_id) not in sent
    messages = build_summary_messages(
        candidates, is_new_subscriber=is_new_subscriber,
        industries=industries, roles=roles,
    )

    for message in messages:
        send_message(chat_id, message)
        time.sleep(1)  # rate limit telegram

    sent = mark_as_sent(sent, chat_id, candidates["url"].dropna())
    return sent, True


def send_summary(target_df):
    subscribers = load_subscribers()
    if not subscribers:
        print("нет подписчиков — рассылать некому")
        return

    sent = prune_sent_vacancies(load_sent_vacancies())

    for chat_id, data in subscribers.items():
        try:
            sent, has_new = _deliver_vacancies(
                chat_id, data.get("industries") or [], data.get("roles") or [],
                target_df, sent,
            )

            if not has_new:
                send_message(chat_id, "Новых интересных вакансий нет :(\n"
                                        "Как только появятся, мы сразу же сообщим!")

            save_sent_vacancies(sent)
        except Exception as error:
            print(f"не удалось отправить {chat_id}: {error}")


# === текстовые команды ===

def _cmd_start(chat_id, subscribers):
    if chat_id not in subscribers:
        subscribers[chat_id] = {"industries": [], "roles": []}
        send_message(
            chat_id,
            "Вы подписались на сводку вакансий!\n"
            "Отправляется автоматически каждые 4 часа.\n"
            "По умолчанию — вакансии из всех сфер и ролей.\n"
            "Отписаться — команда /stop",
            reply_markup=build_main_keyboard(),
        )
    else:
        send_message(
            chat_id,
            "Вы уже подписаны на сводку 🙂\n"
            f"Настроить фильтры — кнопки «{INDUSTRIES_BUTTON_TEXT}» / "
            f"«{ROLES_BUTTON_TEXT}» внизу.",
            reply_markup=build_main_keyboard(),
        )


def _cmd_stop(chat_id, subscribers):
    subscribers.pop(chat_id, None)
    send_message(chat_id, "Вы отписались от сводки.", reply_markup={"remove_keyboard": True})


def _send_filter_menu(chat_id, subscribers, filter_key):
    if chat_id not in subscribers:
        send_message(chat_id, "Сначала подпишитесь: /start")
        return

    spec = _FILTERS[filter_key]
    selected = spec["get"](subscribers, chat_id)
    send_message(
        chat_id,
        f"{spec['menu_title']} ({spec['text'](selected)}):",
        reply_markup=spec["keyboard"](selected),
    )


# показываем топ навыков с учётом текущих фильтров подписчика (сферы/роли)
def _cmd_top_skills(chat_id, subscribers):
    if chat_id not in subscribers:
        send_message(chat_id, "Сначала подпишитесь: /start")
        return

    industries = get_industries(subscribers, chat_id)
    roles = get_roles(subscribers, chat_id)

    message = build_top_skills_message(industries, roles)
    send_message(chat_id, message)


def _cmd_view_all(chat_id, subscribers):
    if chat_id not in subscribers:
        send_message(chat_id, "Сначала подпишитесь: /start")
        return

    target_df = _load_latest_vacancies()
    if target_df.empty:
        send_message(
            chat_id,
            "Сводка ещё не готова — вакансии обновляются раз в 4 часа, загляните чуть позже 🙂",
        )
        return

    industries = get_industries(subscribers, chat_id)
    roles = get_roles(subscribers, chat_id)

    candidates = filter_vacancies(target_df, industries=industries, roles=roles)

    if candidates.empty:
        send_message(chat_id, "По выбранным фильтрам сейчас нет вакансий за неделю.")
        return

    messages = build_summary_messages(
        candidates, is_new_subscriber=True, industries=industries, roles=roles,
    )

    for message in messages:
        send_message(chat_id, message)
        time.sleep(1)


TEXT_COMMANDS = {
    "/start": _cmd_start,
    "/stop": _cmd_stop,
    "/industries": lambda chat_id, subs: _send_filter_menu(chat_id, subs, "ind"),
    INDUSTRIES_BUTTON_TEXT: lambda chat_id, subs: _send_filter_menu(chat_id, subs, "ind"),
    "/roles": lambda chat_id, subs: _send_filter_menu(chat_id, subs, "role"),
    ROLES_BUTTON_TEXT: lambda chat_id, subs: _send_filter_menu(chat_id, subs, "role"),
    "/top_skills": _cmd_top_skills,
    TOP_SKILLS_BUTTON_TEXT: _cmd_top_skills,
    "/view_all": _cmd_view_all,
    VIEW_ALL_BUTTON_TEXT: _cmd_view_all,
    UNSUBSCRIBE_BUTTON_TEXT: _cmd_stop,
}


def _handle_message(message, subscribers):
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")

    if not chat_id:
        return

    handler = TEXT_COMMANDS.get(text)
    if handler:
        handler(chat_id, subscribers)


# === callback-кнопки выбора сфер/ролей ===

def _reset_history(chat_id):
    sent = load_sent_vacancies()
    sent = reset_subscriber_history(sent, chat_id)
    save_sent_vacancies(sent)


def _refresh_keyboard(chat_id, message_id, subscribers, filter_key):
    spec = _FILTERS[filter_key]
    try:
        edit_message_reply_markup(
            chat_id, message_id, spec["keyboard"](spec["get"](subscribers, chat_id)),
        )
    except Exception as error:
        print(f"не удалось обновить клавиатуру {chat_id}: {error}")


def _cb_toggle(chat_id, message_id, subscribers, filter_key, value_key):
    spec = _FILTERS[filter_key]
    values = set(spec["get"](subscribers, chat_id))
    values.symmetric_difference_update({value_key})  # был — убрать, не было — добавить
    spec["set"](subscribers, chat_id, values)

    # выбор поменялся — сбрасываем историю, чтобы под новый фильтр
    # можно было заново увидеть весь пул вакансий
    _reset_history(chat_id)
    _refresh_keyboard(chat_id, message_id, subscribers, filter_key)


def _cb_reset(chat_id, message_id, subscribers, filter_key):
    spec = _FILTERS[filter_key]
    spec["set"](subscribers, chat_id, [])
    _reset_history(chat_id)
    _refresh_keyboard(chat_id, message_id, subscribers, filter_key)


def _cb_confirm(chat_id, callback_id, subscribers):
    answer_callback_query(callback_id, text="Ищу вакансии…")

    target_df = _load_latest_vacancies()
    if target_df.empty:
        send_message(
            chat_id,
            "Сводка ещё не готова — вакансии обновляются раз в 4 часа, загляните чуть позже 🙂",
        )
        return

    industries = get_industries(subscribers, chat_id)
    roles = get_roles(subscribers, chat_id)

    sent = prune_sent_vacancies(load_sent_vacancies())
    sent, has_new = _deliver_vacancies(chat_id, industries, roles, target_df, sent)
    save_sent_vacancies(sent)

    if not has_new:
        send_message(chat_id, "По выбранным фильтрам сейчас нет вакансий за неделю.")


def _handle_callback_query(callback, subscribers):
    callback_id = callback.get("id")
    data = callback.get("data") or ""
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")

    if not chat_id or chat_id not in subscribers:
        answer_callback_query(callback_id)
        return

    if data in ("ind_confirm", "role_confirm"):
        _cb_confirm(chat_id, callback_id, subscribers)
        return

    if data == "ind_reset":
        _cb_reset(chat_id, message_id, subscribers, "ind")
    elif data == "role_reset":
        _cb_reset(chat_id, message_id, subscribers, "role")
    elif data.startswith("ind_toggle:"):
        _cb_toggle(chat_id, message_id, subscribers, "ind", data.split(":", 1)[1])
    elif data.startswith("role_toggle:"):
        _cb_toggle(chat_id, message_id, subscribers, "role", data.split(":", 1)[1])

    answer_callback_query(callback_id)


# === главный цикл опроса ===

def poll_updates():
    offset = _load_offset()
    subscribers = load_subscribers()

    for update in get_updates(offset):
        offset = update["update_id"] + 1

        try:
            if "callback_query" in update:
                _handle_callback_query(update["callback_query"], subscribers)
            else:
                _handle_message(update.get("message") or {}, subscribers)
        except Exception as error:
            print(f"ошибка обработки апдейта {update.get('update_id')}: {error}")

    save_subscribers(subscribers)
    _save_offset(offset)