import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml


PUBLIC_URLS = load_yaml("data/public_urls.yaml")


@pytest.mark.parametrize("page_data", PUBLIC_URLS, ids=lambda page: page["name"])
def test_public_page_has_meta_description(browser, page_data):
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
            "() => document.querySelector('head > meta[name=\"description\"]') !== null",
            timeout=15_000,
        )
        description = page.evaluate(
            """
            () => document
                .querySelector('head > meta[name="description"]')
                ?.getAttribute('content')
                ?.trim() || null
            """
        )
    except PlaywrightTimeoutError:
        description = None

    assert description is not None, (
        f"В HTML-коде страницы '{page_data['name']}' отсутствует "
        f"мета-описание <meta name=\"description\">. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert description, (
        f"У страницы '{page_data['name']}' мета-описание пустое. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )
