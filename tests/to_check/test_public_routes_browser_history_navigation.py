from urllib.parse import urlparse

from tests.helpers import is_tidal_domain


PUBLIC_ROUTE_CHAIN = [
    {
        "name": "Главная страница",
        "url": "https://tidal.com/",
        "path": "/",
        "state": "home",
    },
    {
        "name": "Исследование каталога",
        "url": "https://tidal.com/view/pages/explore",
        "path": "/view/pages/explore",
        "state": "explore",
    },
    {
        "name": "Страница альбома",
        "url": "https://tidal.com/album/432708332",
        "path": "/album/432708332",
        "state": "album",
    },
]

ERROR_MARKERS = [
    "403 forbidden",
    "404 not found",
    "500 internal server error",
    "service unavailable",
    "access denied",
    "page-not-found",
]


def get_path(url: str) -> str:
    path = urlparse(url).path.rstrip("/")

    return path or "/"


def assert_no_error_markers(page, route_name: str) -> None:
    content_lower = page.content().lower()
    found_error_markers = [
        marker for marker in ERROR_MARKERS
        if marker in content_lower
    ]

    assert not found_error_markers, (
        f"После перехода на '{route_name}' страница содержит признаки "
        f"аварийного сценария: {found_error_markers}. "
        f"Финальный URL: {page.url}. "
        f"Title: {page.title().strip()!r}"
    )


def wait_for_expected_state(page, route: dict[str, str]) -> None:
    page.wait_for_function(
        """
        route => {
            const normalizedPath = window.location.pathname.replace(/\\/$/, "") || "/";

            if (normalizedPath !== route.path) {
                return false;
            }

            const main = document.querySelector('main, [data-test="main"]');

            if (!main) {
                return false;
            }

            const mainText = main.innerText || "";
            const title = document.title || "";

            if (route.state === "home") {
                return Boolean(
                    main.querySelector('[data-test^="horizontal-list--"]')
                    || main.querySelector('[data-test="view-all-link"]')
                    || main.querySelector('a[href*="/album/"]')
                    || main.querySelector('a[href*="/playlist/"]')
                    || mainText.trim()
                );
            }

            if (route.state === "explore") {
                return Boolean(
                    /explore/i.test(mainText)
                    || main.querySelector('a[href*="/view/pages/genre_page"]')
                    || main.querySelector('a[href*="/view/pages/moods_page"]')
                    || main.querySelector('[data-test="page-links-cloud-btn"]')
                );
            }

            if (route.state === "album") {
                return Boolean(
                    /cruel, cruel world/i.test(title)
                    || /cruel, cruel world/i.test(mainText)
                    || main.querySelector('a[href*="/track/"]')
                    || main.querySelector('[data-test="track-row"]')
                    || main.querySelector('[data-test="media-item"]')
                    || main.querySelector('button[aria-label="Play"]')
                );
            }

            return false;
        }
        """,
        arg=route,
        timeout=30_000,
    )


def assert_route_state(page, route: dict[str, str], action_name: str) -> None:
    wait_for_expected_state(page, route)

    assert is_tidal_domain(page.url), (
        f"{action_name}: страница '{route['name']}' привела не на домен TIDAL. "
        f"Финальный URL: {page.url}"
    )

    assert get_path(page.url) == route["path"], (
        f"{action_name}: открыт неожиданный маршрут. "
        f"Ожидался путь: {route['path']}. "
        f"Финальный URL: {page.url}"
    )

    assert_no_error_markers(page, route["name"])


def open_route(page, route: dict[str, str]) -> None:
    response = page.goto(
        route["url"],
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    assert response is not None, (
        f"Публичная страница '{route['name']}' не вернула HTTP-ответ "
        f"в браузере. URL: {route['url']}. "
        f"Финальный URL: {page.url}"
    )

    assert response.status < 400, (
        f"Публичная страница '{route['name']}' открылась с HTTP-ошибкой. "
        f"URL: {route['url']}. "
        f"Финальный URL: {page.url}. "
        f"HTTP-статус: {response.status}"
    )

    assert_route_state(page, route, "Прямой переход")


def test_browser_back_and_forward_keep_expected_public_route_state(browser):
    page = browser

    for route in PUBLIC_ROUTE_CHAIN:
        open_route(page, route)

    page.go_back(wait_until="domcontentloaded", timeout=30_000)
    assert_route_state(
        page,
        PUBLIC_ROUTE_CHAIN[1],
        "Первый переход назад браузерной навигацией",
    )

    page.go_back(wait_until="domcontentloaded", timeout=30_000)
    assert_route_state(
        page,
        PUBLIC_ROUTE_CHAIN[0],
        "Второй переход назад браузерной навигацией",
    )

    page.go_forward(wait_until="domcontentloaded", timeout=30_000)
    assert_route_state(
        page,
        PUBLIC_ROUTE_CHAIN[1],
        "Первый переход вперед браузерной навигацией",
    )

    page.go_forward(wait_until="domcontentloaded", timeout=30_000)
    assert_route_state(
        page,
        PUBLIC_ROUTE_CHAIN[2],
        "Второй переход вперед браузерной навигацией",
    )
