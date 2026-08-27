import os
import json
import time
import requests

from history import (
    load_sent_vacancies,
    save_sent_vacancies,
    prune_sent_vacancies,
    get_new_vacancies_for_subscriber,
    mark_as_sent,
)
from summary import build_summary_messages


TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
SUBSCRIBERS_FILE = "data/subscribers.json"
OFFSET_FILE = "data/telegram_offset.txt"


def _token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("не задан TELEGRAM_BOT_TOKEN")
    return token


def _api_url(method):
    return TELEGRAM_API.format(token=_token(), method=method)


# читаем список подписчиков с диска (просто json-файл — для mvp хватит)
def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()

    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as file:
        return set(json.load(file))


def save_subscribers(subscribers):
    os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)

    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as file:
        json.dump(list(subscribers), file)


# offset нужен, чтобы getUpdates не возвращал одни и те же
# сообщения повторно при каждом опросе
def _load_offset():
    if not os.path.exists(OFFSET_FILE):
        return 0

    with open(OFFSET_FILE, "r", encoding="utf-8") as file:
        return int(file.read().strip() or 0)


def _save_offset(offset):
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)

    with open(OFFSET_FILE, "w", encoding="utf-8") as file:
        file.write(str(offset))


def send_telegram_message(chat_id, text):
    response = requests.post(
        _api_url("sendMessage"),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
    )
    response.raise_for_status()


# опрашиваем telegram на новые сообщения и обрабатываем /start и /stop.
# запускается отдельной регулярной джобой (каждые 10-30 секунд),
# независимо от джобы со сводкой раз в 4 часа
def poll_updates():
    offset = _load_offset()
    subscribers = load_subscribers()

    response = requests.get(
        _api_url("getUpdates"),
        params={"offset": offset, "timeout": 5},
    )
    response.raise_for_status()
    updates = response.json().get("result", [])

    for update in updates:
        offset = update["update_id"] + 1

        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")

        if not chat_id:
            continue

        if text == "/start":
            if chat_id not in subscribers:
                subscribers.add(chat_id)
                send_telegram_message(
                    chat_id,
                    "Вы подписались на сводку вакансий!\n"
                    "Отправляется автоматически каждые 4 часа.\n"
                    "Сводка придет, когда появятся новые вакансии.\n"
                    "Отписаться — команда /stop",
                )

        elif text == "/stop":
            subscribers.discard(chat_id)
            send_telegram_message(chat_id, "Вы отписались от сводки.")

    save_subscribers(subscribers)
    _save_offset(offset)


# рассылаем сводку подписчикам — каждому только те вакансии,
# которые лично ему ещё не отправляли
def send_summary(target_df):
    subscribers = load_subscribers()

    if not subscribers:
        print("нет подписчиков — рассылать некому")
        return

    sent = prune_sent_vacancies(load_sent_vacancies())

    for chat_id in subscribers:
        new_vacancies = get_new_vacancies_for_subscriber(target_df, sent, chat_id)

        if new_vacancies.empty:
            continue

        is_new_subscriber = str(chat_id) not in sent

        messages = build_summary_messages(new_vacancies, is_new_subscriber)

        try:
            for message in messages:
                send_telegram_message(chat_id, message)
                time.sleep(1)  # rate limit telegram

            sent = mark_as_sent(sent, chat_id, new_vacancies["url"].dropna())
            save_sent_vacancies(sent)

        except Exception as error:
            print(f"не удалось отправить {chat_id}: {error}")