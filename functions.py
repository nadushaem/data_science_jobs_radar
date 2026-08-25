from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import re


# парсит одну вакансию и возвращает словарь для нее
def parse_card(card, base_url):
    title_element = card.find("a", class_="title")
    title = title_element.get_text(strip=True) if title_element else None

    company_element = card.find("p", class_="company-name")
    company = company_element.get_text(strip=True) if company_element else None

    location_block = card.find("div", class_="info")

    if location_block:
        salary_element = location_block.find("span", class_="salary")
        salary = salary_element.get_text(strip=True) if salary_element else None

        if salary_element:
            salary_element.extract()

        location = location_block.get_text(" ", strip=True) or None
    else:
        salary = None
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
    date = date_element.get_text(strip=True) if date_element else None

    link_element = card.find("a", class_="title")
    link = urljoin(base_url, link_element["href"]) if link_element else None

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "work_format": work_format,
        "date": date,
        "url": link,
        "source": "geekjob"
    }


# поиск ключевых слов
def find_keywords(text, keywords):
    if not text:
        return []

    text = text.lower()
    found = []
    for keyword in keywords:
        if keyword.lower() in text:
            found.append(keyword)
    return found


# получаем страницу вакансии
def get_vacancy_soup(url):
    response = requests.get(url)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# получаем текст вакансии
def get_vacancy_text(soup):
    return soup.get_text("\n", strip=True)


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


# собираем текст по всей вакансии
def get_search_text(vacancy):
    parts = [
        vacancy.get("title"),
        vacancy.get("description"),
        vacancy.get("specialization"),
        vacancy.get("industry"),
    ]

    text_parts = []

    for part in parts:
        if isinstance(part, list):
            text_parts.extend(part)

        elif part:
            text_parts.append(str(part))

    return " ".join(text_parts)


# схлопываем пробелы вокруг / и - , чтобы "ai / ml" == "ai/ml"
def _normalize_for_matching(text):
    text = text.lower()
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


# поиск интересных должностей по ключевым словам
def find_roles(title, role_taxonomy):
    if not title:
        return []

    title = _normalize_for_matching(title)

    found = []
    for canonical_role, aliases in role_taxonomy.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(_normalize_for_matching(alias)) + r"\b"

            if re.search(pattern, title):
                found.append(canonical_role)
                break  # одна роль — не дублируем по разным алиасам

    return found


# исключаем неинтересные должности
def find_excluded_roles(title, excluded_roles):
    if not title:
        return []

    title = title.lower()

    return [
        role
        for role in excluded_roles
        if role.lower() in title
    ]

