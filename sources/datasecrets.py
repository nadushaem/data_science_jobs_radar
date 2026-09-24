import json
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from pipeline.keywords import LEVEL_TAXONOMY, SKILLS_VOCABULARY
from pipeline.parsing import find_keywords, guess_level, parse_salary

SOURCE_NAME = "datasecrets"
BASE_URL = "https://datasecrets.ru"
JOBS_URL = f"{BASE_URL}/jobs"

# у источника нет дат публикации — храним, когда вакансия впервые
# попалась нам на глаза, и дальше работаем с этим как с published_at
STATE_FILE = "data/datasecrets_seen.json"
STATE_RETENTION_DAYS = 90

MIN_REQUEST_DELAY = 2
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ds-jobs-radar/1.0)"}

# подписи, по которым на карточке лежат значения
CARD_LABELS = ("Зарплата", "Опыт работы", "Позиция")
EMPTY_VALUES = {"не указано", "не указана", "-", ""}


def load_seen():
    if not os.path.exists(STATE_FILE):
        return {}

    with open(STATE_FILE, encoding="utf-8") as file:
        return json.load(file)


def save_seen(seen):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(seen, file, ensure_ascii=False, indent=2)


# для вакансий с доски: известные — со старой датой, новые — с текущей.
# пропавшие с доски держим ещё retention_days, вдруг вернутся
def update_seen(seen, vacancy_ids, retention_days=STATE_RETENTION_DAYS):
    now_iso = datetime.now().isoformat()
    cutoff = datetime.now() - timedelta(days=retention_days)

    updated = {vacancy_id: seen.get(vacancy_id, now_iso) for vacancy_id in vacancy_ids}

    for vacancy_id, first_seen in seen.items():
        if vacancy_id in updated:
            continue
        if datetime.fromisoformat(first_seen) >= cutoff:
            updated[vacancy_id] = first_seen

    return updated


def _get(url, max_retries=4):
    for attempt in range(max_retries):
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 5 * (attempt + 1)))
            print(f"datasecrets: 429, ждём {wait} сек ({attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue

        response.raise_for_status()
        return response

    response.raise_for_status()
    return response


def _clean(value):
    if not value:
        return None
    return None if value.strip().lower() in EMPTY_VALUES else value.strip()


# подзаголовок карточки — "Офис в Москве", город оттуда идёт в location
def _parse_location(subtitle):
    subtitle = _clean(subtitle)
    if not subtitle:
        return None

    return re.sub(r"^офис\s+в\s+", "", subtitle.lower()).strip() or None


# значения лежат парами span-ов: подпись + само значение
def _parse_labeled_values(card):
    values = {}

    for block in card.find_all("div"):
        spans = block.find_all("span", recursive=False)
        if len(spans) != 2:
            continue

        label = spans[0].get_text(strip=True)
        if label in CARD_LABELS:
            values[label] = spans[1].get_text(strip=True)

    return values


# теги направления/области (MLE, NLP, Data Engineering) — последний блок карточки
def _parse_tags(card):
    blocks = card.find_all("div", recursive=False)
    if len(blocks) < 4:
        return []

    tags = [span.get_text(strip=True) for span in blocks[-1].find_all("span")]
    return [tag for tag in tags if tag]


def parse_card(card):
    href = card.get("href")
    blocks = card.find_all("div", recursive=False)
    header = blocks[0] if blocks else card

    # в шапке первым идёт span с названием компании, alt логотипа — запасной вариант
    company_element = header.find("span")
    company = company_element.get_text(strip=True) if company_element else None
    if not _clean(company):
        logo = card.find("img")
        company = logo.get("alt") if logo else None

    title_element = card.find(["h1", "h2", "h3"])
    subtitle_element = card.find("h4")
    values = _parse_labeled_values(card)

    return {
        "vacancy_id": href.rsplit("/", 1)[-1],
        "title": title_element.get_text(strip=True) if title_element else None,
        "company": _clean(company),
        "location": _parse_location(
            subtitle_element.get_text(strip=True) if subtitle_element else None
        ),
        "work_format": _clean(values.get("Позиция")),
        "salary_text": _clean(values.get("Зарплата")),
        "tags": _parse_tags(card),
        "url": urljoin(BASE_URL, href),
        "source": SOURCE_NAME,
    }


# карточка = ссылка вида /jobs/1681, дубли (ссылка-картинка + ссылка-текст) убираем
def find_cards(soup):
    cards = {}

    for link in soup.find_all("a", href=True):
        if re.fullmatch(r"/jobs/\d+", link["href"]):
            cards.setdefault(link["href"], link)

    return list(cards.values())


# описание — единственный крупный блок со списками и параграфами.
# берём самый компактный подходящий контейнер: вложенные друг в друга
# div-ы дают тот же текст, но с лишней обвязкой сверху
def parse_description(soup, min_items=3, min_length=200):
    soup = BeautifulSoup(str(soup), "html.parser")

    for tag in soup.find_all(["header", "footer", "nav", "script", "style"]):
        tag.decompose()

    candidates = []

    for block in soup.find_all(["article", "section", "div"]):
        if len(block.find_all(["p", "li"])) < min_items:
            continue

        text = block.get_text(" ", strip=True)
        if len(text) >= min_length:
            candidates.append(text)

    if candidates:
        return min(candidates, key=len)

    body = soup.find("body")
    return body.get_text(" ", strip=True) if body else None


def fetch_vacancies(days=7, max_vacancies=None):
    cutoff = datetime.now() - timedelta(days=days)

    soup = BeautifulSoup(_get(JOBS_URL).text, "html.parser")
    cards = [parse_card(card) for card in find_cards(soup)]

    seen = update_seen(load_seen(), [card["vacancy_id"] for card in cards])
    save_seen(seen)

    vacancies = []

    for card in cards:
        first_seen = pd.Timestamp(seen[card.pop("vacancy_id")])
        if first_seen < cutoff:
            continue

        card["published_at"] = first_seen
        card.update(parse_salary(card.pop("salary_text", None)))

        tags = card.pop("tags", [])
        card["specialization"] = tags or None

        try:
            time.sleep(MIN_REQUEST_DELAY)
            vacancy_soup = BeautifulSoup(_get(card["url"]).text, "html.parser")
            card["description"] = parse_description(vacancy_soup)

        except requests.RequestException as error:
            print(f"Ошибка: {card['title']}")
            print(error)
            card["description"] = None

        # навыки из описания + теги с карточки, как в geekjob
        skills = find_keywords(card.get("description"), SKILLS_VOCABULARY)
        card["skills"] = sorted({*skills, *(tag.lower() for tag in tags)})
        card["level"] = guess_level(card["title"], LEVEL_TAXONOMY)

        vacancies.append(card)

        if max_vacancies and len(vacancies) >= max_vacancies:
            break

    return vacancies
