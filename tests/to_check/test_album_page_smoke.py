from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


ALBUM_TITLE = "Cruel, Cruel World"
ALBUM_URL = "https://tidal.com/album/432708332"
ALBUM_PATH = "/album/432708332"

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
        f"Страница альбома содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def has_album_title(page) -> bool:
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
            arg=ALBUM_TITLE,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def has_album_cover(page) -> bool:
    try:
        page.wait_for_function(
            """
            () => {
                const main = document.querySelector('main, [data-test="main"]');

                if (!main) {
                    return false;
                }

                const images = [...main.querySelectorAll("img")];

                return images.some(image => {
                    const rect = image.getBoundingClientRect();
                    const source = image.currentSrc || image.src || "";

                    return (
                        rect.width >= 120
                        && rect.height >= 120
                        && (
                            source.includes("resources.tidal.com/images/")
                            || image.closest('[data-test="cover-art"]')
                        )
                    );
                });
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def has_album_content_block(page) -> bool:
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
                        || main.querySelector('[data-test="media-table"]')
                        || main.querySelector('[data-test="play-all"]')
                        || main.querySelector('[data-test="track-row"]')
                        || main.querySelector('[data-test="media-item"]')
                        || main.querySelector('[data-test="play-button"]')
                        || main.querySelector('button[aria-label="Play"]')
                    )
                );
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def test_album_page_opens_with_title_cover_and_main_content(browser):
    page = browser

    response = page.goto(
        ALBUM_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Страница альбома не вернула HTTP-ответ в браузере. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Страница альбома открылась с HTTP-ошибкой. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Страница альбома привела не на домен TIDAL. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == ALBUM_PATH, (
        f"Страница альбома открыла неожиданный маршрут. "
        f"Ожидался путь: {ALBUM_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page)

    assert has_album_title(page), (
        f"На странице альбома не найдено ожидаемое название. "
        f"Ожидалось: {ALBUM_TITLE!r}. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )

    assert has_album_cover(page), (
        f"На странице альбома не найдена видимая обложка. "
        f"Ожидалось изображение TIDAL в основном контейнере <main>. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )

    assert has_album_content_block(page), (
        f"На странице альбома не найден основной контентный блок. "
        f"Ожидался <main> с треками, кнопкой Play или ссылками на треки. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
