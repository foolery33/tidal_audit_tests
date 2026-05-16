from urllib.parse import parse_qs, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


SEARCH_QUERY = "lola young"
SEARCH_URL = "https://tidal.com/search?q=lola%20young"
SEARCH_PATH = "/search"

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


def get_query_param(url: str, name: str) -> str | None:
    values = parse_qs(urlparse(url).query).get(name)

    if not values:
        return None

    return values[0]


def has_search_query_in_page(page, search_query: str) -> bool:
    try:
        page.wait_for_function(
            """
            query => {
                const normalizedQuery = query.trim().toLowerCase();
                const title = document.title.toLowerCase();
                const main = document.querySelector('main, [data-test="main"]');
                const mainText = (main?.innerText || "").toLowerCase();
                const searchInputs = [
                    ...document.querySelectorAll('input[type="search"], input[aria-label="Search"]')
                ];

                return Boolean(
                    title.includes(normalizedQuery)
                    || mainText.includes(normalizedQuery)
                    || searchInputs.some(input => (
                        input.value || input.getAttribute("value") || ""
                    ).trim().toLowerCase() === normalizedQuery)
                );
            }
            """,
            arg=search_query,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def wait_for_search_results_content(page) -> None:
    page.wait_for_function(
        """
        () => {
            const main = document.querySelector('main, [data-test="main"]');

            if (!main) {
                return false;
            }

            return Boolean(
                document.title
                || main.innerText?.trim()
                || main.querySelector('[data-test^="horizontal-list--"]')
                || main.querySelector('[data-test="grid-item-detail-text-title"]')
                || main.querySelector('a[href*="/artist/"]')
                || main.querySelector('a[href*="/album/"]')
                || main.querySelector('a[href*="/track/"]')
            );
        }
        """,
        timeout=30_000,
    )


def test_search_results_page_opens_and_shows_query(browser):
    page = browser

    response = page.goto(
        SEARCH_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Страница результатов поиска не вернула HTTP-ответ в браузере. "
        f"URL: {SEARCH_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Страница результатов поиска открылась с HTTP-ошибкой. "
        f"URL: {SEARCH_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert is_tidal_domain(page.url), (
        f"Страница результатов поиска привела не на домен TIDAL. "
        f"URL: {SEARCH_URL}. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == SEARCH_PATH, (
        f"Страница результатов поиска открыла неожиданный маршрут. "
        f"Ожидался путь: {SEARCH_PATH}. "
        f"Финальный URL: {page.url}"
    )

    assert get_query_param(page.url, "q") == SEARCH_QUERY, (
        f"В финальном URL страницы результатов поиска отсутствует ожидаемый "
        f"поисковый запрос. Ожидался q={SEARCH_QUERY!r}. "
        f"Финальный URL: {page.url}"
    )

    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"Страница результатов поиска содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"URL: {SEARCH_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    wait_for_search_results_content(page)

    assert has_search_query_in_page(page, SEARCH_QUERY), (
        f"Поисковый запрос не отображается в заголовке страницы или основном "
        f"контенте страницы результатов поиска. "
        f"Ожидался запрос: {SEARCH_QUERY!r}. "
        f"URL: {SEARCH_URL}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}. "
        f"Title: {page.title().strip()!r}"
    )
