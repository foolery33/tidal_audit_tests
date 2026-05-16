import json

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml


PUBLIC_URLS = load_yaml("data/public_urls.yaml")
EXPECTED_SCHEMA_TYPE = "WebApplication"
EXPECTED_SCHEMA_CONTEXTS = {
    "http://schema.org",
    "https://schema.org",
}
REQUIRED_SCHEMA_FIELDS = [
    "@context",
    "@type",
    "name",
    "applicationCategory",
    "applicationSubCategory",
    "downloadUrl",
    "thumbnailUrl",
    "browserRequirements",
    "operatingSystem",
]


def flatten_json_ld_items(json_ld_data):
    if isinstance(json_ld_data, list):
        return json_ld_data

    if isinstance(json_ld_data, dict) and isinstance(json_ld_data.get("@graph"), list):
        return json_ld_data["@graph"]

    return [json_ld_data]


def parse_json_ld_scripts(script_texts):
    parsed_items = []
    invalid_scripts = []

    for script_text in script_texts:
        try:
            parsed_items.extend(flatten_json_ld_items(json.loads(script_text)))
        except json.JSONDecodeError as error:
            invalid_scripts.append(str(error))

    return parsed_items, invalid_scripts


@pytest.mark.parametrize("page_data", PUBLIC_URLS, ids=lambda page: page["name"])
def test_public_page_has_expected_structured_data(browser, page_data):
    page = browser

    response = page.goto(
        page_data["url"],
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Страница '{page_data['name']}' не вернула HTTP-ответ в браузере. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}"
    )

    try:
        page.wait_for_function(
            """
            () => document.querySelectorAll(
                'script[type="application/ld+json"]'
            ).length > 0
            """,
            timeout=15_000,
        )
    except PlaywrightTimeoutError:
        pass

    script_texts = page.evaluate(
        """
        () => Array.from(
            document.querySelectorAll('script[type="application/ld+json"]')
        ).map(script => script.textContent.trim()).filter(Boolean)
        """
    )

    assert script_texts, (
        f"В HTML-коде страницы '{page_data['name']}' отсутствуют "
        f"структурированные данные JSON-LD. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    structured_data_items, invalid_scripts = parse_json_ld_scripts(script_texts)

    assert not invalid_scripts, (
        f"На странице '{page_data['name']}' найдены невалидные JSON-LD скрипты. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Ошибки парсинга: {invalid_scripts}"
    )

    expected_schema = next(
        (
            item
            for item in structured_data_items
            if isinstance(item, dict)
            and item.get("@type") == EXPECTED_SCHEMA_TYPE
            and item.get("@context") in EXPECTED_SCHEMA_CONTEXTS
        ),
        None,
    )

    assert expected_schema is not None, (
        f"На странице '{page_data['name']}' не найдены структурированные "
        f"данные ожидаемого формата: @context schema.org и "
        f"@type {EXPECTED_SCHEMA_TYPE!r}. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Найденные типы: {[item.get('@type') for item in structured_data_items if isinstance(item, dict)]}"
    )

    missing_fields = [
        field
        for field in REQUIRED_SCHEMA_FIELDS
        if not str(expected_schema.get(field, "")).strip()
    ]

    assert not missing_fields, (
        f"В структурированных данных страницы '{page_data['name']}' "
        f"отсутствуют обязательные поля: {missing_fields}. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )
