from urllib.parse import urlparse

import pytest

from tests.helpers import PROJECT_ROOT, load_yaml


ACCOUNT_URLS = load_yaml("data/account_urls.yaml")


def normalize_url(url: str) -> str:
    parsed_url = urlparse(url)

    return parsed_url._replace(fragment="", query="").geturl().rstrip("/")


@pytest.mark.parametrize("page_data", ACCOUNT_URLS, ids=lambda page: page["name"])
def test_account_page_has_canonical_link(browser, page_data):
    page = browser
    html_path = PROJECT_ROOT / page_data["html_path"]

    assert html_path.exists(), (
        f"Не найден сохраненный HTML-снимок страницы аккаунта "
        f"'{page_data['name']}'. Файл: {html_path}"
    )

    page.set_content(html_path.read_text(encoding="utf-8"), wait_until="domcontentloaded")

    canonical_href = page.evaluate(
        """
        () => document
            .querySelector('head > link[rel="canonical"]')
            ?.getAttribute('href')
            ?.trim() || null
        """
    )

    assert canonical_href is not None, (
        f"В HTML-коде страницы аккаунта '{page_data['name']}' отсутствует "
        f"каноническая ссылка <link rel=\"canonical\">. "
        f"URL: {page_data['url']}. "
        f"Файл: {html_path}"
    )

    assert canonical_href, (
        f"У страницы аккаунта '{page_data['name']}' canonical-ссылка пустая. "
        f"URL: {page_data['url']}. "
        f"Файл: {html_path}"
    )

    assert normalize_url(canonical_href) == normalize_url(page_data["url"]), (
        f"Canonical страницы аккаунта '{page_data['name']}' не совпадает "
        f"с ожидаемым URL. "
        f"URL: {page_data['url']}. "
        f"Файл: {html_path}. "
        f"Canonical: {canonical_href!r}"
    )
