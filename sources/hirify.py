import re
from urllib.parse import urljoin
from datetime import datetime, timedelta
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

from parsing import guess_level
from keywords import LEVEL_TAXONOMY


SOURCE_NAME = "hirify"
BASE_URL = "https://hirify.me/"


# парсит одну карточку вакансии из списка
def parse_card(card, base_url):
    link_element = card.find("a", class_="vacancy-card-link")
    url = urljoin(base_url, link_element["href"]) if link_element else None

    title_element = card.find("h3", class_="title")
    title = title_element.get_text(strip=True) if title_element else None

    company_element = card.find("div", class_="company")
    company = company_element.get_text(strip=True) if company_element else None

    date_element = card.find("div", class_="date-full")
    date_text = date_element.get_text(strip=True) if date_element else None

    # зп на листинге — просто число + значок валюты, без "от"/"до"
    salary_element = card.find("div", class_="salary")
    salary_text = salary_element.get_text(" ", strip=True) if salary_element else None

    return {
        "title": title,
        "company": company,
        "url": url,
        "date_text": date_text,
        "salary_text": salary_text,
        "source": SOURCE_NAME,
    }


# получаем страницу вакансии
def get_vacancy_soup(url):
    response = requests.get(url)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# описание = tldr (короткая выжимка) + основной текст,
# так классификатору по ключевым словам будет проще зацепиться за сферу
def parse_description(soup):
    parts = []

    tldr = soup.find("div", class_="vacancy-tldr__text")
    if tldr:
        parts.append(tldr.get_text(" ", strip=True))

    description = soup.find("div", class_="description")
    if description:
        # убираем кнопку "показать контакты" — она попадает в текст вместе с остальным
        button = description.find("button")
        if button:
            button.extract()

        parts.append(description.get_text(" ", strip=True))

    return " ".join(parts) if parts else None


# на странице вакансии есть подписанный блок с деталями —
# берем его вместо неупорядоченных тегов на листинге, это надежнее
def parse_common_tags(soup):
    block = soup.find("div", class_="vacancy-common-tags")
    if not block:
        return {}

    result = {}
    for item in block.find_all("div", class_="common-detail-item"):
        label = item.find("div", class_="label")
        value = item.find("div", class_="value")

        if label and value:
            result[label.get_text(strip=True)] = value.get_text(strip=True)

    return result


# полный список навыков (на листинге он обрезан кнопкой "+N skills")
def parse_skills(soup):
    tags_block = soup.find("div", class_="vacancy-detail-tags")
    if not tags_block:
        return []

    return [
        tag.get_text(strip=True)
        for tag in tags_block.find_all("button", class_="tag")
    ]


# парсим зп вида "300 000 ₽" — на hirify это одно число без "от"/"до",
# трактуем его как нижнюю границу ("от")
def parse_salary(value):
    result = {
        "salary_min": None,
        "salary_max": None,
        "currency": None,
        "salary_period": "month",  # на hirify зп всегда указана за месяц
    }

    if not value:
        return result

    raw = str(value).lower().replace("\xa0", " ")

    if "₽" in raw or "руб" in raw:
        result["currency"] = "RUB"
    elif "$" in raw or "usd" in raw:
        result["currency"] = "USD"
    elif "€" in raw or "eur" in raw:
        result["currency"] = "EUR"
    elif "£" in raw or "gbp" in raw:
        result["currency"] = "GBP"

    numbers = re.findall(r"\d[\d ]*\d|\d", raw)
    values = [int(n.replace(" ", "")) for n in numbers]
    values = [v for v in values if v < 10_000_000]

    if not values:
        return result

    if "от " in raw:
        result["salary_min"] = values[0]
    elif "до " in raw:
        result["salary_max"] = values[0]
    elif len(values) >= 2:
        result["salary_min"] = min(values[:2])
        result["salary_max"] = max(values[:2])
    else:
        result["salary_min"] = values[0]

    return result


# парсим относительную дату вида "9 минут назад", "2 часа назад", "3 дня назад"
def parse_relative_date(value):
    if not value:
        return pd.NaT

    text = str(value).lower().strip()
    now = datetime.now()

    if text == "сегодня":
        return pd.Timestamp(now)
    if text == "вчера":
        return pd.Timestamp(now - timedelta(days=1))

    match = re.match(
        r"(\d+)\s+(минут\w*|час\w*|день|дня|дней|недел\w*|месяц\w*)", text,
    )
    if not match:
        return pd.NaT

    amount = int(match.group(1))
    unit = match.group(2)

    if unit.startswith("минут"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("час"):
        delta = timedelta(hours=amount)
    elif unit.startswith("недел"):
        delta = timedelta(weeks=amount)
    elif unit.startswith("месяц"):
        delta = timedelta(days=amount * 30)
    else:  # день / дня / дней
        delta = timedelta(days=amount)

    return pd.Timestamp(now - delta)


# получаем вакансии с hirify за последние N дней (фильтр remote_type=russia)
def fetch_vacancies(days=7, max_pages=100):
    cutoff = datetime.now() - timedelta(days=days)
    vacancies = []

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}?page={page}&remote_type=russia"

        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("div", class_="vacancy-card")

        if not cards:
            break

        page_has_recent = False

        for card in cards:
            vacancy = parse_card(card, BASE_URL)
            if not vacancy["url"]:
                continue

            published_at = parse_relative_date(vacancy.pop("date_text", None))
            if pd.isna(published_at) or published_at < cutoff:
                continue

            page_has_recent = True
            vacancy["published_at"] = published_at

            salary_data = parse_salary(vacancy.pop("salary_text", None))
            vacancy.update(salary_data)

            try:
                vacancy_soup = get_vacancy_soup(vacancy["url"])
                vacancy["description"] = parse_description(vacancy_soup)

                common_tags = parse_common_tags(vacancy_soup)
                vacancy["work_format"] = common_tags.get("Формат работы")
                vacancy["location"] = common_tags.get("Страна")

                grade_text = common_tags.get("Грейд")
                vacancy["level"] = (
                    guess_level(grade_text, LEVEL_TAXONOMY) if grade_text
                    else guess_level(vacancy["title"], LEVEL_TAXONOMY)
                )

                time.sleep(0.5)

                vacancy["skills"] = parse_skills(vacancy_soup)

            except requests.RequestException as error:
                print(f"Ошибка: {vacancy['title']}")
                print(error)

                vacancy["description"] = None
                vacancy["work_format"] = None
                vacancy["location"] = None
                vacancy["level"] = guess_level(vacancy["title"], LEVEL_TAXONOMY)
                vacancy["skills"] = []

            vacancies.append(vacancy)

        if not page_has_recent:
            break

    return vacancies