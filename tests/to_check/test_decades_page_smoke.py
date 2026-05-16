from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


DECADES_URL = "https://tidal.com/view/pages/genre_decades"
DECADES_PATH = "/view/pages/genre_decades"

ERROR_MARKERS = [
    "403 forbidden",
    "404 not found",
    "500 internal server error",
    "service unavailable",
    "access denied",
    "page-not-found",
]


def get_path(url: str) -> str:
    return urlparse(url).path.rstrip("/")


def has_decades_content_block(page) -> bool:
    try:
        page.wait_for_function(
            """
            () => {
                const main = document.querySelector('main, [data-test="main"]');

                if (!main) {
                    return false;
                }

                const mainText = main.innerText || "";

                return Boolean(
                    /decades/i.test(mainText)
                    || main.querySelector('a[href*="/view/pages/m_1950s"]')
                    || main.querySelector('a[href*="/view/pages/m_1960s"]')
                    || main.querySelector('a[href*="/view/pages/m_1970s"]')
                    || main.querySelector('[data-test="page-links-cloud-btn"]')
                    || main.querySelector('[data-test^="page-link-"]')
                );
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def test_decades_page_opens_with_main_content(browser):
    page = browser

    response = page.goto(
        DECADES_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Страница десятилетий не вернула HTTP-ответ в браузере. "
        f"URL: {DECADES_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Страница десятилетий открылась с HTTP-ошибкой. "
        f"URL: {DECADES_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Страница десятилетий привела не на домен TIDAL. "
        f"URL: {DECADES_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == DECADES_PATH, (
        f"Страница десятилетий открыла неожиданный маршрут. "
        f"Ожидался путь: {DECADES_PATH}. "
        f"Финальный URL: {page.url}"
    )

    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"Страница десятилетий содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {DECADES_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert has_decades_content_block(page), (
        f"На странице десятилетий не найден основной контентный блок. "
        f"Ожидался <main> с заголовком Decades или ссылками на десятилетия. "
        f"URL: {DECADES_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
