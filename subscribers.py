import os
import json

SUBSCRIBERS_FILE = "data/subscribers.json"


def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return {}

    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as file:
        raw = json.load(file)

    # старый формат — просто список chat_id, конвертируем на лету
    if isinstance(raw, list):
        return {int(chat_id): {"industries": []} for chat_id in raw}

    return {
        int(chat_id): {"industries": data.get("industries") or []}
        for chat_id, data in raw.items()
    }


def save_subscribers(subscribers):
    os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)

    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {str(chat_id): data for chat_id, data in subscribers.items()},
            file, ensure_ascii=False,
        )


def get_industries(subscribers, chat_id):
    return subscribers[chat_id].get("industries") or []


def set_industries(subscribers, chat_id, industries):
    subscribers[chat_id]["industries"] = sorted(set(industries))