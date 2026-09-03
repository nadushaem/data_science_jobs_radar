import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("не задан TELEGRAM_BOT_TOKEN")
    return token


def _api_url(method):
    return TELEGRAM_API.format(token=_token(), method=method)


def get_updates(offset):
    response = requests.get(
        _api_url("getUpdates"), params={"offset": offset, "timeout": 5},
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("result", [])


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = requests.post(_api_url("sendMessage"), json=payload, timeout=15)
    response.raise_for_status()
    return response.json().get("result")


def edit_message_reply_markup(chat_id, message_id, reply_markup):
    response = requests.post(
        _api_url("editMessageReplyMarkup"),
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": reply_markup,
        },
        timeout=15,
    )
    response.raise_for_status()


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    try:
        response = requests.post(_api_url("answerCallbackQuery"), json=payload, timeout=15)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"не удалось ответить на callback {callback_query_id}: {error}")