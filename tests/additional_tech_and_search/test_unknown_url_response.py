import random
import time
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import load_yaml, is_tidal_domain


UNKNOWN_URLS = load_yaml("data/unknown_urls.yaml")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOT_FOUND_HTML_PATH = PROJECT_ROOT / "html_pages" / "TIDAL_not_found.html"


ANTIBOT_MARKERS = [
    "you have been blocked",
    "something about the behaviour of the browser has caught our attention",
    "there is a robot on the same network",
    "check if cookies are allowed in your browser",
    "our systems have detected unusual traffic",
    "unusual traffic from your computer network",
    "this page checks to see if it's really you",
    "datadome",
    "captcha",
    "challenge",
]

NOT_FOUND_PLACEHOLDER_DATA_TEST = "page-not-found"
NOT_FOUND_PLACEHOLDER_MARKER = f'data-test="{NOT_FOUND_PLACEHOLDER_DATA_TEST}"'
NOT_FOUND_PLACEHOLDER_SELECTOR = f'[data-test="{NOT_FOUND_PLACEHOLDER_DATA_TEST}"]'
NOT_FOUND_PLACEHOLDER_TIMEOUT_MS = 60_000


def find_markers(text: str, markers: list[str]) -> list[str]:
    text_lower = text.lower()

    return [
        marker for marker in markers
        if marker in text_lower
    ]


def get_visible_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=10_000)
    except PlaywrightTimeoutError:
        return ""


def expected_not_found_placeholder_exists() -> bool:
    return NOT_FOUND_PLACEHOLDER_MARKER in NOT_FOUND_HTML_PATH.read_text(encoding="utf-8")


def wait_for_not_found_placeholder(page) -> bool:
    try:
        page.locator(NOT_FOUND_PLACEHOLDER_SELECTOR).first.wait_for(
            state="attached",
            timeout=NOT_FOUND_PLACEHOLDER_TIMEOUT_MS,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def save_debug_artifacts(page, test_name: str) -> None:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    safe_name = (
        test_name
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )

    screenshot_path = artifacts_dir / f"{safe_name}.png"
    html_path = artifacts_dir / f"{safe_name}.html"

    page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")


@pytest.mark.parametrize("page_data", UNKNOWN_URLS, ids=lambda page: page["name"])
def test_unknown_url_shows_not_found_placeholder(browser, page_data):
    assert expected_not_found_placeholder_exists(), (
        f"В эталонной HTML-заглушке нет ожидаемого DOM-маркера "
        f"{NOT_FOUND_PLACEHOLDER_MARKER}. "
        f"Файл: {NOT_FOUND_HTML_PATH}"
    )

    page = browser

    time.sleep(random.uniform(2.0, 4.0))

    response = page.goto(
        page_data["url"],
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    time.sleep(random.uniform(3.0, 5.0))

    try:
        page.locator("#app-loader").wait_for(state="hidden", timeout=10_000)
    except PlaywrightTimeoutError:
        pass

    has_not_found_stub = wait_for_not_found_placeholder(page)

    current_url = page.url
    title = page.title().strip()
    html = page.content()
    visible_text = get_visible_body_text(page)

    combined_text = "\n".join([
        current_url,
        title,
        visible_text,
        html,
    ])

    found_antibot_markers = find_markers(combined_text, ANTIBOT_MARKERS)

    if found_antibot_markers:
        save_debug_artifacts(page, page_data["name"])

    assert not found_antibot_markers, (
        f"Несуществующий URL заблокирован антибот-защитой. "
        f"Исходный URL: {page_data['url']}. "
        f"Финальный URL: {current_url}. "
        f"Title: {title!r}. "
        f"Найденные признаки защиты: {found_antibot_markers}"
    )

    assert response is not None, (
        f"Несуществующий URL не вернул HTTP-ответ в браузере. "
        f"URL: {page_data['url']}. "
        f"Финальный URL: {current_url}"
    )

    assert is_tidal_domain(current_url), (
        f"Несуществующий URL привёл не на домен TIDAL. "
        f"Исходный URL: {page_data['url']}. "
        f"Финальный URL: {current_url}"
    )

    assert response.status < 500, (
        f"Несуществующий URL вернул серверную ошибку. "
        f"Исходный URL: {page_data['url']}. "
        f"Финальный URL: {current_url}. "
        f"HTTP-статус: {response.status}"
    )

    if not has_not_found_stub:
        save_debug_artifacts(page, page_data["name"])

    assert has_not_found_stub, (
        f"Несуществующий URL не показывает явную заглушку отсутствующей страницы. "
        f"Ожидался DOM-маркер [data-test='page-not-found']. "
        f"Исходный URL: {page_data['url']}. "
        f"Финальный URL: {current_url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {title!r}. "
        f"Видимый текст страницы: {visible_text[:500]!r}"
    )
