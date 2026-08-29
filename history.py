import os
import json
from datetime import datetime, timedelta


SENT_FILE = "data/sent_vacancies.json"
SENT_RETENTION_DAYS = 30  # с запасом больше, чем окно фетча (7 дней)


# реестр по подписчикам: {chat_id (str): {url: дата_отправки в iso}}
def load_sent_vacancies():
    if not os.path.exists(SENT_FILE):
        return {}

    with open(SENT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_sent_vacancies(sent):
    os.makedirs(os.path.dirname(SENT_FILE), exist_ok=True)

    with open(SENT_FILE, "w", encoding="utf-8") as file:
        json.dump(sent, file, ensure_ascii=False, indent=2)


# чистим записи старше retention_days у каждого подписчика,
# чтобы файл не рос бесконечно
def prune_sent_vacancies(sent, retention_days=SENT_RETENTION_DAYS):
    cutoff = datetime.now() - timedelta(days=retention_days)
    pruned = {}

    for chat_id, urls in sent.items():
        kept = {
            url: sent_at
            for url, sent_at in urls.items()
            if datetime.fromisoformat(sent_at) >= cutoff
        }

        if kept:
            pruned[chat_id] = kept

    return pruned


# новые для конкретного подписчика вакансии — те, что ему ещё не отправляли.
# для нового подписчика (его нет в реестре) вернёт все is_target вакансии
def get_new_vacancies_for_subscriber(target_df, sent, chat_id):
    seen_urls = set(sent.get(str(chat_id), {}).keys())
    return target_df[~target_df["url"].isin(seen_urls)]


# отмечаем url как отправленные конкретному подписчику
def mark_as_sent(sent, chat_id, urls):
    chat_key = str(chat_id)
    now_iso = datetime.now().isoformat()

    chat_sent = sent.setdefault(chat_key, {})
    chat_sent.update({url: now_iso for url in urls if url})

    return sent

# сбрасываем историю отправленных вакансий конкретному подписчику —
# нужно при смене сфер, чтобы под новый фильтр видео было "с нуля"
def reset_subscriber_history(sent, chat_id):
    sent.pop(str(chat_id), None)
    return sent