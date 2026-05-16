from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


ARTIST_NAME = "Felix Ames"
ARTIST_URL = "https://tidal.com/artist/30416609"
ARTIST_PATH = "/artist/30416609"

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
        f"Страница исполнителя содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {ARTIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def has_artist_name(page) -> bool:
    try:
        page.wait_for_function(
            """
            expectedName => {
                const title = document.title.toLowerCase();
                const main = document.querySelector('main, [data-test="main"]');
                const mainText = (main?.innerText || "").toLowerCase();
                const artistName = document.querySelector('[data-test="artist-name"]');

                return (
                    title.includes(expectedName.toLowerCase())
                    || mainText.includes(expectedName.toLowerCase())
                    || (artistName?.innerText || "")
                        .toLowerCase()
                        .includes(expectedName.toLowerCase())
                );
            }
            """,
            arg=ARTIST_NAME,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def has_artist_key_blocks(page) -> bool:
    try:
        page.wait_for_function(
            """
            () => {
                const main = document.querySelector('main, [data-test="main"]');

                if (!main) {
                    return false;
                }

                const mainText = main.innerText || "";
                const hasSectionHeading = (
                    /top tracks/i.test(mainText)
                    || /popular/i.test(mainText)
                    || /albums/i.test(mainText)
                    || /singles/i.test(mainText)
                    || /spotlight/i.test(mainText)
                    || /videos/i.test(mainText)
                );
                const hasMediaLinks = Boolean(
                    main.querySelector('a[href*="/track/"]')
                    || main.querySelector('a[href*="/album/"]')
                    || main.querySelector('a[href*="/video/"]')
                );
                const hasControls = Boolean(
                    main.querySelector('[data-test="play-button"]')
                    || main.querySelector('[data-test="play-all"]')
                    || main.querySelector('[data-test="mix-button"]')
                    || main.querySelector('[data-test="follow-text-button"]')
                    || main.querySelector('button[aria-label="Play"]')
                    || main.querySelector('button[aria-label*="Follow"]')
                    || main.querySelector('button[aria-label*="Add"]')
                    || main.querySelector('button[aria-label="Show options"]')
                );

                return Boolean(
                    mainText.trim()
                    && (
                        hasSectionHeading
                        || hasMediaLinks
                        || hasControls
                        || main.querySelector('[data-test="artist-profile"]')
                        || main.querySelector('[data-test="artist-profile-header"]')
                        || main.querySelector('[data-test="artist-meta"]')
                        || main.querySelector('[data-test^="album-card-"]')
                        || main.querySelector('[data-test^="horizontal-list--"]')
                        || main.querySelector('[data-test="grid-item-detail-text-title"]')
                        || main.querySelector('[data-test="media-item"]')
                    )
                );
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def test_artist_page_opens_with_name_and_key_blocks(browser):
    page = browser

    response = page.goto(
        ARTIST_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Страница исполнителя не вернула HTTP-ответ в браузере. "
        f"URL: {ARTIST_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Страница исполнителя открылась с HTTP-ошибкой. "
        f"URL: {ARTIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Страница исполнителя привела не на домен TIDAL. "
        f"URL: {ARTIST_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == ARTIST_PATH, (
        f"Страница исполнителя открыла неожиданный маршрут. "
        f"Ожидался путь: {ARTIST_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page)

    assert has_artist_name(page), (
        f"На странице исполнителя не найдено ожидаемое имя. "
        f"Ожидалось: {ARTIST_NAME!r}. "
        f"URL: {ARTIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )

    assert has_artist_key_blocks(page), (
        f"На странице исполнителя не найдены ключевые блоки страницы. "
        f"Ожидался <main> с треками, альбомами/релизами, кнопками действий "
        f"или ссылками на контент исполнителя. "
        f"URL: {ARTIST_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
