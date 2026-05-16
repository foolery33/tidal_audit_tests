from collections import defaultdict

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml


PUBLIC_URLS = load_yaml("data/public_urls.yaml")


def get_title_text(page) -> str | None:
    try:
        page.wait_for_function(
            "() => document.querySelector('head > title') !== null",
            timeout=15_000,
        )
        return page.evaluate(
            "() => document.querySelector('head > title')?.textContent?.trim() || null"
        )
    except PlaywrightTimeoutError:
        return None


def normalize_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def test_public_page_titles_are_unique(browser):
    page = browser
    titles_by_page = []

    for page_data in PUBLIC_URLS:
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

        title = get_title_text(page)

        assert title, (
            f"У страницы '{page_data['name']}' отсутствует или пустой title. "
            f"URL: {page_data['url']}. "
            f"Финальный URL: {page.url}. "
            f"HTTP-статус: {response.status}"
        )

        titles_by_page.append(
            {
                "name": page_data["name"],
                "url": page_data["url"],
                "final_url": page.url,
                "title": title,
                "normalized_title": normalize_title(title),
            }
        )

    pages_by_title = defaultdict(list)

    for page_title_data in titles_by_page:
        pages_by_title[page_title_data["normalized_title"]].append(page_title_data)

    duplicated_titles = {
        pages[0]["title"]: [
            {
                "name": page_data["name"],
                "url": page_data["url"],
                "final_url": page_data["final_url"],
            }
            for page_data in pages
        ]
        for pages in pages_by_title.values()
        if len(pages) > 1
    }

    assert not duplicated_titles, (
        f"В контрольной выборке найдены дублирующиеся заголовки страниц: "
        f"{duplicated_titles}"
    )
