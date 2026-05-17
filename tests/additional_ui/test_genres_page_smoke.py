from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


GENRES_URL = "https://tidal.com/view/pages/genre_page"
GENRES_PATH = "/view/pages/genre_page"

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


def has_genres_content_block(page) -> bool:
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
                    /genres/i.test(mainText)
                    || main.querySelector('a[href*="/view/pages/genre_"]')
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


def test_genres_page_opens_with_main_content(browser):
    page = browser

    response = page.goto(
        GENRES_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Раздел жанров не вернул HTTP-ответ в браузере. "
        f"URL: {GENRES_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Раздел жанров открылся с HTTP-ошибкой. "
        f"URL: {GENRES_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Раздел жанров привел не на домен TIDAL. "
        f"URL: {GENRES_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == GENRES_PATH, (
        f"Раздел жанров открыл неожиданный маршрут. "
        f"Ожидался путь: {GENRES_PATH}. "
        f"Финальный URL: {page.url}"
    )

    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"Раздел жанров содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {GENRES_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert has_genres_content_block(page), (
        f"В разделе жанров не найден основной контентный блок страницы. "
        f"Ожидался <main> с заголовком Genres или ссылками на жанры. "
        f"URL: {GENRES_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
