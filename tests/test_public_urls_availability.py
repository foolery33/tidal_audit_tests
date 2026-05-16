import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

from tests.helpers import load_yaml, is_tidal_domain


PUBLIC_URLS = load_yaml("data/public_urls.yaml")


@pytest.mark.parametrize("page_data", PUBLIC_URLS, ids=lambda page: page["name"])
def test_public_url_is_available_for_user(browser, page_data):
    try:
        browser.get(page_data["url"])

        WebDriverWait(browser, 30).until(
            lambda driver: driver.execute_script("return document.readyState") in ["interactive", "complete"]
        )

        current_url = browser.current_url
        title = browser.title.strip()
        page_source = browser.page_source

        assert is_tidal_domain(current_url), (
            f"Публичный URL '{page_data['name']}' после открытия привёл не на домен TIDAL. "
            f"Исходный URL: {page_data['url']}. "
            f"Финальный URL: {current_url}"
        )

        assert title, (
            f"У публичной страницы '{page_data['name']}' отсутствует title. "
            f"URL: {page_data['url']}. "
            f"Финальный URL: {current_url}"
        )

        assert len(page_source) > 500, (
            f"Публичная страница '{page_data['name']}' загрузила подозрительно короткий HTML. "
            f"URL: {page_data['url']}. "
            f"Финальный URL: {current_url}. "
            f"Размер HTML: {len(page_source)} символов"
        )

        page_source_lower = page_source.lower()

        error_markers = [
            "403 forbidden",
            "404 not found",
            "500 internal server error",
            "service unavailable",
            "access denied",
        ]

        found_errors = [
            marker for marker in error_markers
            if marker in page_source_lower
        ]

        assert not found_errors, (
            f"На публичной странице '{page_data['name']}' найдены признаки ошибки: "
            f"{found_errors}. "
            f"URL: {page_data['url']}. "
            f"Финальный URL: {current_url}"
        )

    except TimeoutException:
        pytest.fail(
            f"Публичный URL '{page_data['name']}' не загрузился за допустимое время. "
            f"URL: {page_data['url']}"
        )
    except WebDriverException as error:
        pytest.fail(
            f"При открытии публичного URL '{page_data['name']}' произошла ошибка браузера. "
            f"URL: {page_data['url']}. "
            f"Ошибка: {error}"
        )