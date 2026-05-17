from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


HOME_URL = "https://tidal.com/"

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
    "page-not-found",
]


def has_home_content_block(page) -> bool:
    try:
        page.wait_for_function(
            """
            () => {
                const main = document.querySelector('main, [data-test="main"]');

                if (!main) {
                    return false;
                }

                return Boolean(
                    main.querySelector('[data-test^="horizontal-list--"]')
                    || main.querySelector('[data-test="view-all-link"]')
                    || main.querySelector('a[href*="/album/"]')
                    || main.querySelector('a[href*="/playlist/"]')
                );
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def test_home_page_opens_with_content_block(browser):
    page = browser

    response = page.goto(
        HOME_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Главная страница не вернула HTTP-ответ в браузере. "
        f"URL: {HOME_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Главная страница открылась с HTTP-ошибкой. "
        f"URL: {HOME_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Главная страница привела не на домен TIDAL. "
        f"URL: {HOME_URL}. "
        f"Финальный URL: {page.url}"
    )

    title = page.title().strip()
    content = page.content()
    content_lower = content.lower()

    found_antibot_markers = [
        marker for marker in ANTIBOT_MARKERS
        if marker in page.url.lower() or marker in title.lower() or marker in content_lower
    ]

    assert not found_antibot_markers, (
        f"Главная страница заблокирована антибот-защитой. "
        f"URL: {HOME_URL}. "
        f"Финальный URL: {page.url}. "
        f"Title: {title!r}. "
        f"Найденные признаки защиты: {found_antibot_markers}"
    )

    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"Главная страница содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {HOME_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert has_home_content_block(page), (
        f"На главной странице не найден ключевой контентный блок. "
        f"Ожидался <main> с контентным модулем, ссылкой view-all, "
        f"альбомами или плейлистами. "
        f"URL: {HOME_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {title!r}"
    )
