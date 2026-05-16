from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


HOME_URL = "https://tidal.com/"
EXPLORE_PATH = "/view/pages/explore"


def get_path(url: str) -> str:
    return urlparse(url).path.rstrip("/")


def click_explore_link(page) -> None:
    explore_link = page.locator('a[data-test="sidebar-explore"]').first

    try:
        explore_link.wait_for(state="visible", timeout=10_000)
    except PlaywrightTimeoutError:
        explore_link = page.locator(f'a[href*="{EXPLORE_PATH}"]').first
        explore_link.wait_for(state="visible", timeout=10_000)

    explore_link.click()


def test_home_page_navigates_to_explore_catalog(browser):
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

    click_explore_link(page)
    page.wait_for_url(f"**{EXPLORE_PATH}", timeout=30_000)

    assert get_path(page.url) == EXPLORE_PATH, (
        f"Переход в раздел исследования каталога открыл неожиданный маршрут. "
        f"Ожидался путь: {EXPLORE_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert is_tidal_domain(page.url), (
        f"Переход в раздел исследования каталога привел не на домен TIDAL. "
        f"Финальный URL: {page.url}"
    )

    assert page.locator('main, [data-test="main"]').first.is_visible(timeout=10_000), (
        f"После перехода в раздел исследования каталога не найден основной "
        f"контентный контейнер <main>. Финальный URL: {page.url}"
    )
