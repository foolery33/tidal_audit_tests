from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


ROBOTS_TXT_URL = "https://tidal.com/robots.txt"
EXPLICIT_ABSENCE_STATUS_CODES = {403, 404, 410}
ROBOTS_TXT_MARKERS = ("user-agent", "disallow", "allow", "sitemap")
ACCESS_DENIED_MARKERS = ("accessdenied", "access denied")


def get_page_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=5_000).strip()
    except PlaywrightTimeoutError:
        return ""


def test_robots_txt_is_available_or_absence_is_explicit(browser):
    page = browser

    response = page.goto(
        ROBOTS_TXT_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"robots.txt не вернул HTTP-ответ в браузере. "
        f"URL: {ROBOTS_TXT_URL}. "
        f"Финальный URL: {page.url}"
    )

    final_url = page.url
    parsed_final_url = urlparse(final_url)
    final_hostname = parsed_final_url.hostname or ""

    assert final_hostname == "tidal.com" or final_hostname.endswith(".tidal.com"), (
        f"robots.txt перенаправил не на домен TIDAL. "
        f"Исходный URL: {ROBOTS_TXT_URL}. "
        f"Финальный URL: {final_url}. "
        f"HTTP-статус: {response.status}"
    )

    assert parsed_final_url.path == "/robots.txt", (
        f"robots.txt должен проверяться по ожидаемому адресу. "
        f"Исходный URL: {ROBOTS_TXT_URL}. "
        f"Финальный URL: {final_url}. "
        f"HTTP-статус: {response.status}"
    )

    body = get_page_body_text(page)
    body_lower = body.lower()

    if response.status in EXPLICIT_ABSENCE_STATUS_CODES:
        if response.status == 403:
            assert any(marker in body_lower for marker in ACCESS_DENIED_MARKERS), (
                f"robots.txt вернул 403, но ответ не похож на явный отказ доступа. "
                f"Исходный URL: {ROBOTS_TXT_URL}. "
                f"Финальный URL: {final_url}. "
                f"Тело страницы: {body[:300]!r}"
            )

        return

    assert response.status == 200, (
        f"robots.txt вернул неожиданный HTTP-статус. "
        f"Исходный URL: {ROBOTS_TXT_URL}. "
        f"Финальный URL: {final_url}. "
        f"HTTP-статус: {response.status}. "
        f"Тело страницы: {body[:300]!r}"
    )

    assert body, (
        f"robots.txt доступен, но тело ответа пустое. "
        f"URL: {final_url}. "
        f"Content-Type: {response.headers.get('content-type', '')!r}"
    )

    assert any(marker in body_lower for marker in ROBOTS_TXT_MARKERS), (
        f"robots.txt доступен, но не похож на файл robots.txt. "
        f"URL: {final_url}. "
        f"Content-Type: {response.headers.get('content-type', '')!r}. "
        f"Тело ответа: {body[:300]!r}"
    )
