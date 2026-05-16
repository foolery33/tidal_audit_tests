from urllib.parse import urlparse

import pytest

from tests.helpers import load_yaml


ACCOUNT_URLS = load_yaml("data/account_urls.yaml")
PROTECTED_STATUS_CODES = {401, 403}
LOGIN_HOSTS = {
    "login.tidal.com",
    "auth.tidal.com",
}
PRIVATE_CONTENT_MARKERS = [
    "Log In Details",
    "Current Password",
    "General Info",
    "Your Subscription",
    "Payment Method",
    "Offline Devices",
    "Notifications",
    "No active subscription",
    "Edit Information",
    "Delete account",
]


def is_login_url(url: str) -> bool:
    hostname = urlparse(url).hostname or ""

    return hostname in LOGIN_HOSTS


def get_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=5_000)
    except Exception:
        return ""


@pytest.mark.parametrize("page_data", ACCOUNT_URLS, ids=lambda page: page["name"])
def test_private_account_page_does_not_expose_content_without_auth(browser, page_data):
    page = browser
    page.context.clear_cookies()

    response = page.goto(
        page_data["url"],
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Приватная страница аккаунта '{page_data['name']}' не вернула "
        f"HTTP-ответ в браузере. URL: {page_data['url']}. "
        f"Финальный URL: {page.url}"
    )

    body_text = get_body_text(page)
    page_html = page.content()
    combined_content = f"{body_text}\n{page_html}"
    found_private_markers = [
        marker for marker in PRIVATE_CONTENT_MARKERS
        if marker in combined_content
    ]

    assert not found_private_markers, (
        f"Приватная страница аккаунта '{page_data['name']}' без авторизации "
        f"отдала признаки персонального содержимого: {found_private_markers}. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    is_protected_response = (
        response.status in PROTECTED_STATUS_CODES
        or is_login_url(page.url)
    )

    assert is_protected_response, (
        f"Приватная страница аккаунта '{page_data['name']}' без авторизации "
        f"не вернула явный отказ доступа и не перенаправила на страницу входа. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
