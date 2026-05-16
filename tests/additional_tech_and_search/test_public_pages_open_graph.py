import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml


PUBLIC_URLS = load_yaml("data/public_urls.yaml")
REQUIRED_OPEN_GRAPH_PROPERTIES = [
    "og:title",
    "og:description",
    "og:image",
    "og:url",
]


@pytest.mark.parametrize("page_data", PUBLIC_URLS, ids=lambda page: page["name"])
def test_public_page_has_open_graph_markup(browser, page_data):
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
            requiredProperties => requiredProperties.every(property =>
                document.querySelector(`head > meta[property="${property}"]`) !== null
            )
            """,
            arg=REQUIRED_OPEN_GRAPH_PROPERTIES,
            timeout=15_000,
        )
    except PlaywrightTimeoutError:
        pass

    open_graph_values = page.evaluate(
        """
        requiredProperties => Object.fromEntries(
            requiredProperties.map(property => [
                property,
                document
                    .querySelector(`head > meta[property="${property}"]`)
                    ?.getAttribute("content")
                    ?.trim() || null
            ])
        )
        """,
        REQUIRED_OPEN_GRAPH_PROPERTIES,
    )

    missing_properties = [
        property_name
        for property_name, content in open_graph_values.items()
        if content is None
    ]

    assert not missing_properties, (
        f"В HTML-коде страницы '{page_data['name']}' отсутствуют "
        f"обязательные поля Open Graph: {missing_properties}. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    empty_properties = [
        property_name
        for property_name, content in open_graph_values.items()
        if content == ""
    ]

    assert not empty_properties, (
        f"У страницы '{page_data['name']}' есть пустые поля Open Graph: "
        f"{empty_properties}. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )
