import json
import os

from pipeline.keywords import ROLE_RENAMES

SUBSCRIBERS_FILE = "data/subscribers.json"


# старые ключи ролей переводим на новые, файл перезапишется при ближайшем save
def _migrate_roles(roles):
    return sorted({ROLE_RENAMES.get(role, role) for role in roles or []})


def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return {}

    with open(SUBSCRIBERS_FILE, encoding="utf-8") as file:
        raw = json.load(file)

    if isinstance(raw, list):
        return {int(chat_id): {"industries": [], "roles": []} for chat_id in raw}

    return {
        int(chat_id): {
            "industries": data.get("industries") or [],
            "roles": _migrate_roles(data.get("roles")),
        }
        for chat_id, data in raw.items()
    }


def save_subscribers(subscribers):
    os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)

    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {str(chat_id): data for chat_id, data in subscribers.items()},
            file,
            ensure_ascii=False,
        )


def get_industries(subscribers, chat_id):
    return subscribers[chat_id].get("industries") or []


def set_industries(subscribers, chat_id, industries):
    subscribers[chat_id]["industries"] = sorted(set(industries))


def get_roles(subscribers, chat_id):
    return subscribers[chat_id].get("roles") or []


def set_roles(subscribers, chat_id, roles):
    subscribers[chat_id]["roles"] = sorted(set(roles))
