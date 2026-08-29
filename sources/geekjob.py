import re
from urllib.parse import urljoin
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

from parsing import find_keywords, guess_level
from keywords import SKILLS_VOCABULARY, LEVEL_TAXONOMY


SOURCE_NAME = "geekjob"
BASE_URL = "https://geekjob.ru/vacancies"


# парсит одну вакансию и возвращает словарь для нее
def parse_card(card, base_url):
    title_element = card.find("a", class_="title")
    title = title_element.get_text(strip=True) if title_element else None

    company_element = card.find("p", class_="company-name")
    company = company_element.get_text(strip=True) if company_element else None

    location_block = card.find("div", class_="info")

    if location_block:
        salary_element = location_block.find("span", class_="salary")
        salary_text = salary_element.get_text(strip=True) if salary_element else None

        if salary_element:
            salary_element.extract()

        location = location_block.get_text(" ", strip=True) or None
    else:
        salary_text = None
        location = None

    work_format_element = card.find(
        "span",
        class_=["inhouse-label", "remote-label"]
    )
    work_format = (
        work_format_element.get_text(strip=True)
        if work_format_element
        else None
    )

    date_element = card.find("time", class_="datetime-info")
    date_text = date_element.get_text(strip=True) if date_element else None

    link_element = card.find("a", class_="title")
    link = urljoin(base_url, link_element["href"]) if link_element else None

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary_text": salary_text,
        "work_format": work_format,
        "date_text": date_text,
        "url": link,
        "source": SOURCE_NAME,
    }


# получаем страницу вакансии
def get_vacancy_soup(url):
    response = requests.get(url)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# парсим описание вакансии
def parse_description(soup):
    description = soup.find("div", id="vacancy-description")

    if description:
        return description.get_text(" ", strip=True)

    return None


# парсим теги со страницы вакансии
def parse_tags(soup):
    tags_block = soup.find("div", class_="tags-list")

    if not tags_block:
        return {
            "specialization": None,
            "industry": None,
            "level": None
        }

    tags = {
        "specialization": [],
        "industry": [],
        "level": []
    }

    category_mapping = {
        "Специализация": "specialization",
        "Отрасль и сфера применения": "industry",
        "Уровень должности": "level"
    }

    current_category = None

    for element in tags_block.find_all(["b", "a"]):

        if element.name == "b":
            category_name = element.get_text(strip=True)
            current_category = category_mapping.get(category_name)

        elif (
            element.name == "a"
            and "chip" in element.get("class", [])
            and current_category
        ):
            tags[current_category].append(
                element.get_text(strip=True)
            )

    return {
        key: values if values else None
        for key, values in tags.items()
    }


# парсим зп (формат geekjob: "от 150 000 ₽", "100k-150k", "150 000 - 200 000 руб." и тд)
def parse_salary(value):
    result = {
        "salary_min": None,
        "salary_max": None,
        "currency": None,
        "salary_period": None,
    }

    if not value:
        return result

    raw = str(value).lower()
    raw = raw.replace("\xa0", " ")
    raw = raw.replace(",", ".")

    if any(x in raw for x in ["₽", "руб", "rub"]):
        result["currency"] = "RUB"
    elif any(x in raw for x in ["$", "usd"]):
        result["currency"] = "USD"
    elif any(x in raw for x in ["€", "eur"]):
        result["currency"] = "EUR"
    elif any(x in raw for x in ["£", "gbp"]):
        result["currency"] = "GBP"

    if any(x in raw for x in ["год", "year", "/year", "per year"]):
        result["salary_period"] = "year"
    elif any(x in raw for x in ["час", "hour", "/hour", "per hour"]):
        result["salary_period"] = "hour"
    else:
        result["salary_period"] = "month"

    numbers = re.findall(
        r"\d+(?:\.\d+)?\s*(?:k|к|тыс\.?)?",
        raw,
    )

    values = []

    for item in numbers:
        item = item.replace(" ", "")

        if re.search(r"(k|к|тыс)", item):
            number = float(
                re.sub(r"(k|к|тыс\.?)", "", item)
            )
            number *= 1000
        else:
            number = float(item)

        values.append(
            int(number) if number.is_integer() else number
        )

    values = [value for value in values if value < 10_000_000]
    if not values:
        return result

    if any(x in raw for x in ["от ", "from ", ">="]):
        result["salary_min"] = values[0]

    elif any(x in raw for x in ["до ", "up to ", "<="]):
        result["salary_max"] = values[0]

    elif len(values) >= 2:
        result["salary_min"] = min(values[:2])
        result["salary_max"] = max(values[:2])

    else:
        result["salary_min"] = values[0]

    return result


# парсим дату вида "17 августа"
def parse_geekjob_date(value):
    if not value:
        return pd.NaT

    months = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }

    match = re.match(r"(\d{1,2})\s+([а-яё]+)", str(value).lower().strip())

    if not match or match.group(2) not in months:
        return pd.NaT

    day, month = int(match.group(1)), months[match.group(2)]
    now = datetime.now()
    year = now.year

    date = pd.Timestamp(year=year, month=month, day=day)
    if date > pd.Timestamp(now) + pd.Timedelta(days=1):
        date = date.replace(year=year - 1)

    return date


# получаем вакансии с geekjob за последние N дней
def fetch_vacancies(days=7, max_pages=30):
    cutoff = datetime.now() - timedelta(days=days)
    vacancies = []

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/{page}"

        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("li", class_="collection-item avatar")

        if not cards:
            break

        page_has_recent = False

        for card in cards:
            vacancy = parse_card(card, BASE_URL)
            published_at = parse_geekjob_date(vacancy.pop("date_text", None))

            if pd.isna(published_at) or published_at < cutoff:
                continue

            page_has_recent = True
            vacancy["published_at"] = published_at

            try:
                vacancy_soup = get_vacancy_soup(vacancy["url"])
                vacancy["description"] = parse_description(vacancy_soup)
                vacancy.update(parse_tags(vacancy_soup))

            except requests.RequestException as error:
                print(f"Ошибка: {vacancy['title']}")
                print(error)

                vacancy["description"] = None
                vacancy["specialization"] = None
                vacancy["industry"] = None
                vacancy["level"] = None

            vacancy["skills"] = find_keywords(vacancy.get("description"), SKILLS_VOCABULARY)
            if not vacancy.get("level"):
                vacancy["level"] = guess_level(vacancy["title"], LEVEL_TAXONOMY)

            salary_data = parse_salary(vacancy.pop("salary_text", None))
            vacancy.update(salary_data)

            vacancies.append(vacancy)

        if not page_has_recent:
            break

    return vacancies