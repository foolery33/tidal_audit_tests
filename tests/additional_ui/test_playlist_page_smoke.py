from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


PLAYLIST_TITLE = "123"
PLAYLIST_URL = "https://tidal.com/playlist/7475b9fb-c4b7-4188-8d3f-b88181c5eeb7"
PLAYLIST_PATH = "/playlist/7475b9fb-c4b7-4188-8d3f-b88181c5eeb7"

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


def assert_no_error_markers(page) -> None:
    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"Страница плейлиста содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {PLAYLIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def has_playlist_title(page) -> bool:
    try:
        page.wait_for_function(
            """
            expectedTitle => {
                const title = document.title.toLowerCase();
                const main = document.querySelector('main, [data-test="main"]');
                const mainText = (main?.innerText || "").toLowerCase();

                return (
                    title.includes(expectedTitle.toLowerCase())
                    || mainText.includes(expectedTitle.toLowerCase())
                );
            }
            """,
            arg=PLAYLIST_TITLE,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def has_playlist_main_content(page) -> bool:
    try:
        page.wait_for_function(
            """
            () => {
                const main = document.querySelector('main, [data-test="main"]');

                if (!main) {
                    return false;
                }

                return Boolean(
                    main.innerText?.trim()
                    && (
                        main.querySelector('a[href*="/track/"]')
                        || main.querySelector('a[href*="/artist/"]')
                        || main.querySelector('[data-test="media-table"]')
                        || main.querySelector('[data-test="play-all"]')
                        || main.querySelector('[data-test="track-row"]')
                        || main.querySelector('[data-test="media-item"]')
                        || main.querySelector('[data-test="play-button"]')
                        || main.querySelector('button[aria-label="Play"]')
                        || main.querySelector('button[aria-label="Show options"]')
                    )
                );
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def test_playlist_page_opens_with_title_and_main_content(browser):
    page = browser

    response = page.goto(
        PLAYLIST_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Страница плейлиста не вернула HTTP-ответ в браузере. "
        f"URL: {PLAYLIST_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Страница плейлиста открылась с HTTP-ошибкой. "
        f"URL: {PLAYLIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Страница плейлиста привела не на домен TIDAL. "
        f"URL: {PLAYLIST_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == PLAYLIST_PATH, (
        f"Страница плейлиста открыла неожиданный маршрут. "
        f"Ожидался путь: {PLAYLIST_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page)

    assert has_playlist_title(page), (
        f"На странице плейлиста не найдено ожидаемое название. "
        f"Ожидалось: {PLAYLIST_TITLE!r}. "
        f"URL: {PLAYLIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )

    assert has_playlist_main_content(page), (
        f"На странице плейлиста не найдено основное содержимое. "
        f"Ожидался <main> с треками, исполнителями, кнопкой Play "
        f"или действиями плейлиста. "
        f"URL: {PLAYLIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
