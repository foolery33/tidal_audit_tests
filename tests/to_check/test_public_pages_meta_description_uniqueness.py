from collections import defaultdict
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml


PUBLIC_URLS = load_yaml("data/public_urls.yaml")
ENTITY_PATH_PREFIXES = (
    "/artist/",
    "/playlist/",
    "/album/",
    "/@",
)


def is_entity_page(url: str) -> bool:
    path = urlparse(url).path

    return path.startswith(ENTITY_PATH_PREFIXES)


def get_meta_description(page) -> str | None:
    try:
        page.wait_for_function(
            "() => document.querySelector('head > meta[name=\"description\"]') !== null",
            timeout=15_000,
        )
        return page.evaluate(
            """
            () => document
                .querySelector('head > meta[name="description"]')
                ?.getAttribute('content')
                ?.trim() || null
            """
        )
    except PlaywrightTimeoutError:
        return None


def normalize_description(description: str) -> str:
    return " ".join(description.split()).casefold()


def test_public_entity_meta_descriptions_are_not_template_duplicates(browser):
    page = browser
    descriptions_by_page = []

    for page_data in PUBLIC_URLS:
        if not is_entity_page(page_data["url"]):
            continue

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

        description = get_meta_description(page)

        assert description, (
            f"У страницы '{page_data['name']}' отсутствует или пустое "
            f"мета-описание. URL: {page_data['url']}. "
            f"Финальный URL: {page.url}. "
            f"HTTP-статус: {response.status}"
        )

        descriptions_by_page.append(
            {
                "name": page_data["name"],
                "url": page_data["url"],
                "final_url": page.url,
                "description": description,
                "normalized_description": normalize_description(description),
            }
        )

    pages_by_description = defaultdict(list)

    for description_data in descriptions_by_page:
        pages_by_description[description_data["normalized_description"]].append(
            description_data
        )

    duplicated_descriptions = {
        pages[0]["description"]: [
            {
                "name": page_data["name"],
                "url": page_data["url"],
                "final_url": page_data["final_url"],
            }
            for page_data in pages
        ]
        for pages in pages_by_description.values()
        if len(pages) > 1
    }

    assert not duplicated_descriptions, (
        f"В контрольной выборке найдены дословно повторяющиеся "
        f"мета-описания на разных сущностях: {duplicated_descriptions}"
    )
