import random
import time

import pytest

from tests.helpers import load_yaml, is_tidal_domain


PUBLIC_URLS = load_yaml("data/public_urls.yaml")


ANTIBOT_MARKERS = [
    "you have been blocked",
    "something about the behaviour of the browser has caught our attention",
    "there is a robot on the same network",
    "check if cookies are allowed in your browser",
    "if you are using a proxy service",
    "our systems have detected unusual traffic",
    "unusual traffic from your computer network",
    "this page checks to see if it's really you",
    "datadome",
    "captcha",
    "challenge",
]

ERROR_MARKERS = [
    "403 forbidden",
    "404 not found",
    "500 internal server error",
    "service unavailable",
    "access denied",
]


@pytest.mark.parametrize("page_data", PUBLIC_URLS, ids=lambda page: page["name"])
def test_public_url_is_available_for_user(browser, page_data):
    page = browser

    page.goto(page_data["url"], wait_until="domcontentloaded", timeout=30000)

    current_url = page.url
    title = page.title().strip()
    content = page.content()
    content_lower = content.lower()

    found_antibot_markers = [
        marker for marker in ANTIBOT_MARKERS
        if marker in current_url.lower() or marker in title.lower() or marker in content_lower
    ]

    assert not found_antibot_markers, (
        f"Страница '{page_data['name']}' заблокирована антибот-защитой. "
        f"Исходный URL: {page_data['url']}. "
        f"Финальный URL: {current_url}. "
        f"Title: {title!r}. "
        f"Найденные признаки защиты: {found_antibot_markers}"
    )

    assert is_tidal_domain(current_url), (
        f"Публичный URL '{page_data['name']}' привёл не на домен TIDAL. "
        f"Исходный URL: {page_data['url']}. Финальный URL: {current_url}"
    )

    assert title, (
        f"У страницы '{page_data['name']}' отсутствует title. "
        f"URL: {page_data['url']}"
    )

    assert len(content) > 500, (
        f"Страница '{page_data['name']}' загрузила подозрительно короткий HTML. "
        f"Размер: {len(content)} символов"
    )

    found_errors = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_errors, (
        f"На странице '{page_data['name']}' найдены признаки ошибки: {found_errors}. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {current_url}"
    )