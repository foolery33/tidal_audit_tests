from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


EXPLORE_URL = "https://tidal.com/view/pages/explore"
EXPLORE_PATH = "/view/pages/explore"
MOODS_PATH = "/view/pages/moods_page"

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


def wait_for_path(page, expected_path: str) -> None:
    page.wait_for_function(
        """
        expectedPath => window.location.pathname.replace(/\\/$/, "") === expectedPath
        """,
        arg=expected_path,
        timeout=30_000,
    )


def assert_no_error_markers(page, section_name: str) -> None:
    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"{section_name} содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def click_moods_link(page) -> None:
    moods_link = page.locator(
        f'main a[href*="{MOODS_PATH}"], '
        f'[data-test="main"] a[href*="{MOODS_PATH}"]'
    ).first

    try:
        moods_link.wait_for(state="visible", timeout=30_000)
    except PlaywrightTimeoutError:
        page.locator('main, [data-test="main"]').first.wait_for(
            state="visible",
            timeout=10_000,
        )
        moods_link = page.locator(f'a[href*="{MOODS_PATH}"]').first
        moods_link.wait_for(state="visible", timeout=10_000)

    moods_link.scroll_into_view_if_needed(timeout=10_000)
    moods_link.click()


def has_moods_content_block(page) -> bool:
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
                    /moods\\s*&\\s*activities/i.test(mainText)
                    || /moods and activities/i.test(mainText)
                    || main.querySelector('a[href*="/view/pages/mood_"]')
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


def assert_moods_page_opened(page) -> None:
    wait_for_path(page, MOODS_PATH)

    assert is_tidal_domain(page.url), (
        f"Переход в раздел 'Настроения и занятия' привел не на домен TIDAL. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == MOODS_PATH, (
        f"Раздел 'Настроения и занятия' открыл неожиданный маршрут. "
        f"Ожидался путь: {MOODS_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page, "Раздел 'Настроения и занятия'")

    assert has_moods_content_block(page), (
        f"В разделе 'Настроения и занятия' не найден основной контентный блок. "
        f"Ожидался <main> с заголовком Moods & Activities или ссылками "
        f"на страницы настроений/занятий. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def test_explore_page_navigates_to_moods_without_breaking_navigation(browser):
    page = browser

    response = page.goto(
        EXPLORE_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Раздел исследования каталога не вернул HTTP-ответ в браузере. "
        f"URL: {EXPLORE_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Раздел исследования каталога открылся с HTTP-ошибкой. "
        f"URL: {EXPLORE_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Раздел исследования каталога привел не на домен TIDAL. "
        f"URL: {EXPLORE_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == EXPLORE_PATH, (
        f"Раздел исследования каталога открыл неожиданный маршрут. "
        f"Ожидался путь: {EXPLORE_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page, "Раздел исследования каталога")

    click_moods_link(page)
    assert_moods_page_opened(page)

    page.go_back(wait_until="domcontentloaded", timeout=30_000)
    wait_for_path(page, EXPLORE_PATH)

    assert page.locator('main, [data-test="main"]').first.is_visible(timeout=10_000), (
        f"После возврата из раздела 'Настроения и занятия' "
        f"не найден основной контейнер <main>. Финальный URL: {page.url}"
    )

    page.go_forward(wait_until="domcontentloaded", timeout=30_000)
    assert_moods_page_opened(page)
