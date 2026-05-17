import random
import time
import os
from pathlib import Path
from types import MethodType

import pytest
from playwright.sync_api import sync_playwright


AUTH_STATE_PATH = Path(__file__).resolve().parents[1] / ".auth" / "tidal.json"
CHROME_PROFILE_PATH = Path(
    "/Users/admin/Library/Application Support/Google/Chrome/Profile 3"
)
USE_CHROME_PROFILE = False
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)
SAFARI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.0 Safari/605.1.15"
)
SUPPORTED_BROWSERS = ("chrome", "safari", "webkit")
# Change this value for PyCharm runs: "chrome", "safari", or "webkit".
# Set to None to use --tidal-browser, TIDAL_BROWSER, or the default Chrome.
FORCED_BROWSER = "chrome"
SCREEN_SIZE = {"width": 1920, "height": 1080}
TIMEZONE_ID = os.getenv("TIDAL_TIMEZONE", "America/New_York")
HUMAN_BEHAVIOR_ENABLED = os.getenv("TIDAL_HUMAN_BEHAVIOR", "1") != "0"
PAGE_LOAD_DELAY_RANGE = (1.8, 4.5)
ACTION_DELAY_RANGE = (0.35, 1.35)
SCROLL_STEP_RANGE = (180, 520)
MOUSE_MOVE_STEP_RANGE = (8, 18)
CHROME_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--start-maximized",
]


def pytest_addoption(parser):
    parser.addoption(
        "--tidal-browser",
        action="store",
        choices=SUPPORTED_BROWSERS,
        default=None,
        help="Browser for Playwright tests: chrome or safari/webkit.",
    )


def human_pause(min_seconds=None, max_seconds=None):
    if not HUMAN_BEHAVIOR_ENABLED:
        return

    min_seconds = ACTION_DELAY_RANGE[0] if min_seconds is None else min_seconds
    max_seconds = ACTION_DELAY_RANGE[1] if max_seconds is None else max_seconds
    time.sleep(random.uniform(min_seconds, max_seconds))


def move_mouse_like_user(page):
    if not HUMAN_BEHAVIOR_ENABLED:
        return

    start_x = random.randint(80, 320)
    start_y = random.randint(80, 260)
    end_x = random.randint(520, SCREEN_SIZE["width"] - 240)
    end_y = random.randint(220, SCREEN_SIZE["height"] - 240)
    steps = random.randint(*MOUSE_MOVE_STEP_RANGE)

    try:
        page.mouse.move(start_x, start_y)
        human_pause(0.15, 0.45)
        page.mouse.move(end_x, end_y, steps=steps)
    except Exception:
        return


def scroll_like_user(page):
    if not HUMAN_BEHAVIOR_ENABLED:
        return

    try:
        scroll_height = page.evaluate(
            "() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
        )
    except Exception:
        return

    if scroll_height <= SCREEN_SIZE["height"]:
        return

    current_position = 0
    max_position = min(scroll_height - SCREEN_SIZE["height"], random.randint(900, 1800))

    while current_position < max_position:
        current_position += random.randint(*SCROLL_STEP_RANGE)
        page.mouse.wheel(0, current_position)
        human_pause(0.25, 0.9)

    if random.random() < 0.65:
        page.mouse.wheel(0, -random.randint(180, 480))
        human_pause(0.25, 0.8)


def warm_up(page):
    human_pause(2.5, 5.5)
    move_mouse_like_user(page)
    scroll_like_user(page)
    human_pause(1.0, 2.5)


def install_humanized_goto(page):
    original_goto = page.goto

    def goto_with_human_delay(self, *args, **kwargs):
        human_pause(*PAGE_LOAD_DELAY_RANGE)
        response = original_goto(*args, **kwargs)
        human_pause(0.8, 2.2)
        move_mouse_like_user(self)
        if random.random() < 0.75:
            scroll_like_user(self)
        return response

    page.goto = MethodType(goto_with_human_delay, page)


@pytest.fixture(scope="session")
def browser_name(pytestconfig):
    selected_browser = (
        FORCED_BROWSER
        or pytestconfig.getoption("--tidal-browser")
        or os.getenv("TIDAL_BROWSER")
        or "chrome"
    ).lower()

    if selected_browser not in SUPPORTED_BROWSERS:
        raise pytest.UsageError(
            f"Unsupported browser {selected_browser!r}. "
            f"Use one of: {', '.join(SUPPORTED_BROWSERS)}"
        )

    return "webkit" if selected_browser == "safari" else selected_browser


def get_context_options(browser_name, *, use_storage_state=True):
    context_options = {
        "locale": "en-US",
        "viewport": SCREEN_SIZE,
        "screen": SCREEN_SIZE,
        "device_scale_factor": 1,
        "color_scheme": "dark",
        "timezone_id": TIMEZONE_ID,
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        },
        "user_agent": SAFARI_USER_AGENT if browser_name == "webkit" else CHROME_USER_AGENT,
    }

    if use_storage_state and AUTH_STATE_PATH.exists():
        context_options["storage_state"] = str(AUTH_STATE_PATH)

    return context_options


def add_init_scripts(context, browser_name):
    if browser_name == "webkit":
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        return

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = window.chrome || { runtime: {} };
        if (window.navigator.permissions?.query) {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        }
    """)


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def persistent_chrome_context(playwright_instance, browser_name):
    if browser_name != "chrome" or not USE_CHROME_PROFILE:
        yield None
        return

    if not CHROME_PROFILE_PATH.exists():
        raise pytest.UsageError(f"Chrome profile not found: {CHROME_PROFILE_PATH}")

    print(f"TIDAL tests browser: chrome profile {CHROME_PROFILE_PATH}")
    context = playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str(CHROME_PROFILE_PATH.parent),
        headless=False,
        channel="chrome",
        args=[
            *CHROME_LAUNCH_ARGS,
            f"--profile-directory={CHROME_PROFILE_PATH.name}",
        ],
        **get_context_options(browser_name, use_storage_state=False),
    )
    add_init_scripts(context, browser_name)

    yield context

    context.close()


@pytest.fixture(scope="session")
def playwright_browser(playwright_instance, browser_name, persistent_chrome_context):
    if persistent_chrome_context is not None:
        yield None
        return

    if browser_name == "webkit":
        print("TIDAL tests browser: safari/webkit")
        browser = playwright_instance.webkit.launch(headless=False)
    else:
        print("TIDAL tests browser: chrome")
        browser = playwright_instance.chromium.launch(
            headless=False,
            channel="chrome",
            args=CHROME_LAUNCH_ARGS,
        )

    yield browser

    browser.close()


@pytest.fixture
def browser(playwright_browser, persistent_chrome_context, browser_name):
    if persistent_chrome_context is not None:
        page = persistent_chrome_context.new_page()
        install_humanized_goto(page)
        page.goto("https://tidal.com", timeout=60000)
        warm_up(page)

        yield page

        page.close()
        return

    context = playwright_browser.new_context(
        **get_context_options(browser_name),
    )
    add_init_scripts(context, browser_name)

    page = context.new_page()
    install_humanized_goto(page)
    page.goto("https://tidal.com", timeout=60000)
    warm_up(page)

    yield page

    context.close()
