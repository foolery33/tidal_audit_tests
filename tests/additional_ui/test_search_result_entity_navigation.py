from urllib.parse import parse_qs, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.helpers import is_tidal_domain


SEARCH_QUERY = "lola young"
SEARCH_URL = "https://tidal.com/search?q=lola%20young"
SEARCH_PATH = "/search"
ENTITY_PATH_PREFIXES = ("/track/", "/album/", "/artist/")

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


def assert_no_error_markers(page, page_name: str) -> None:
    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"{page_name} содержит признаки аварийного сценария: "
        f"{found_error_markers}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def wait_for_search_results(page) -> None:
    page.wait_for_function(
        """
        () => {
            const main = document.querySelector('main, [data-test="main"]');

            if (!main) {
                return false;
            }

            return Boolean(
                main.querySelector('a[href*="/track/"]')
                || main.querySelector('a[href*="/album/"]')
                || main.querySelector('a[href*="/artist/"]')
            );
        }
        """,
        timeout=30_000,
    )


def get_first_entity_link_data(page) -> dict[str, str | None]:
    return page.evaluate(
        """
        () => {
            const links = [
                ...document.querySelectorAll(
                    'main a[href*="/track/"], '
                    + 'main a[href*="/album/"], '
                    + 'main a[href*="/artist/"]'
                    + ', [data-test="main"] a[href*="/track/"]'
                    + ', [data-test="main"] a[href*="/album/"]'
                    + ', [data-test="main"] a[href*="/artist/"]'
                )
            ];
            const link = links.find(candidate => {
                const rect = candidate.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            }) || links[0];

            return {
                href: link?.href || null,
                text: link?.innerText?.trim() || link?.getAttribute("title") || null,
            };
        }
        """
    )


def click_first_entity_link(page) -> dict[str, str | None]:
    entity_link = page.locator(
        'main a[href*="/track/"], '
        'main a[href*="/album/"], '
        'main a[href*="/artist/"], '
        '[data-test="main"] a[href*="/track/"], '
        '[data-test="main"] a[href*="/album/"], '
        '[data-test="main"] a[href*="/artist/"]'
    ).first

    entity_link.wait_for(state="visible", timeout=30_000)
    entity_link.scroll_into_view_if_needed(timeout=10_000)
    link_data = get_first_entity_link_data(page)
    entity_link.click()

    return link_data


def wait_for_entity_page(page) -> None:
    page.wait_for_function(
        """
        prefixes => prefixes.some(prefix => window.location.pathname.startsWith(prefix))
        """,
        arg=list(ENTITY_PATH_PREFIXES),
        timeout=30_000,
    )


def open_first_entity_link(page) -> dict[str, str | None]:
    link_data = click_first_entity_link(page)

    try:
        wait_for_entity_page(page)
    except PlaywrightTimeoutError:
        if not link_data["href"]:
            raise
        page.goto(link_data["href"], wait_until="domcontentloaded", timeout=30_000)
        wait_for_entity_page(page)

    return link_data


def has_entity_content(page) -> bool:
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
                    || main.querySelector('[data-test="grid-item-detail-text-title"]')
                    || main.querySelector('[data-test="track-row"]')
                    || main.querySelector('[data-test="media-item"]')
                    || main.querySelector('button[data-test="play-button"]')
                    || main.querySelector('a[href*="/artist/"]')
                    || main.querySelector('a[href*="/album/"]')
                    || main.querySelector('a[href*="/track/"]')
                );
            }
            """,
            timeout=30_000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def assert_search_context_restored(page) -> None:
    page.wait_for_function(
        """
        () => window.location.pathname.replace(/\\/$/, "") === "/search"
        """,
        timeout=30_000,
    )

    assert get_query_param(page.url, "q") == SEARCH_QUERY, (
        f"После возврата со страницы сущности потерян поисковый контекст. "
        f"Ожидался q={SEARCH_QUERY!r}. "
        f"Финальный URL: {page.url}"
    )

    wait_for_search_results(page)


def test_search_result_opens_entity_page_without_losing_context(browser):
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
        f"В URL страницы результатов поиска отсутствует ожидаемый запрос. "
        f"Ожидался q={SEARCH_QUERY!r}. "
        f"Финальный URL: {page.url}"
    )

    wait_for_search_results(page)
    assert_no_error_markers(page, "Страница результатов поиска")

    entity_link_data = open_first_entity_link(page)

    target_path = get_path(page.url)

    assert is_tidal_domain(page.url), (
        f"Переход из поисковой выдачи привел не на домен TIDAL. "
        f"Ссылка: {entity_link_data['href']!r}. "
        f"Финальный URL: {page.url}"
    )

    assert target_path.startswith(ENTITY_PATH_PREFIXES), (
        f"Переход из поисковой выдачи открыл не страницу трека, альбома "
        f"или исполнителя. Ссылка: {entity_link_data['href']!r}. "
        f"Текст ссылки: {entity_link_data['text']!r}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page, "Целевая страница сущности")

    assert has_entity_content(page), (
        f"На целевой странице сущности не найден основной контентный блок. "
        f"Ссылка: {entity_link_data['href']!r}. "
        f"Текст ссылки: {entity_link_data['text']!r}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )

    try:
        page.go_back(wait_until="commit", timeout=10_000)
    except PlaywrightTimeoutError:
        if get_path(page.url) != SEARCH_PATH:
            raise
    assert_search_context_restored(page)
