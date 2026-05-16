import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml


PUBLIC_URLS = load_yaml("data/public_urls.yaml")


@pytest.mark.parametrize("page_data", PUBLIC_URLS, ids=lambda page: page["name"])
def test_public_page_has_title_tag(browser, page_data):
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
            "() => document.querySelector('head > title') !== null",
            timeout=15_000,
        )
        title_text = page.evaluate(
            "() => document.querySelector('head > title')?.textContent?.trim() || null"
        )
    except PlaywrightTimeoutError:
        title_text = None

    page_title = page.title().strip()

    assert title_text is not None, (
        f"В HTML-коде страницы '{page_data['name']}' отсутствует тег <title>. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert title_text, (
        f"У страницы '{page_data['name']}' тег <title> пустой. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"document.title: {page_title!r}"
    )
