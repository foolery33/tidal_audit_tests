import random
import time
import os
from pathlib import Path
from types import MethodType

import pytest
from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_STATE_PATH = PROJECT_ROOT / ".auth" / "tidal.json"
DEFAULT_CHROME_USER_DATA_DIR = PROJECT_ROOT / ".chrome-user-data"
CHROME_USER_AGENT = os.getenv("TIDAL_CHROME_USER_AGENT")
SAFARI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.0 Safari/605.1.15"
)
SUPPORTED_BROWSERS = ("chrome", "firefox", "safari", "webkit")
FORCED_BROWSER = "firefox"
SCREEN_SIZE = {"width": 1920, "height": 1080}
TIMEZONE_ID = os.getenv("TIDAL_TIMEZONE", "America/New_York")
HUMAN_BEHAVIOR_ENABLED = True
PAGE_LOAD_DELAY_RANGE = (1.8, 4.5)
ACTION_DELAY_RANGE = (0.35, 1.35)
SCROLL_STEP_RANGE = (180, 520)
MOUSE_MOVE_STEP_RANGE = (8, 18)
CHROME_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-infobars",
]


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def pytest_addoption(parser):
    parser.addoption(
        "--tidal-browser",
        action="store",
        choices=SUPPORTED_BROWSERS,
        default=None,
        help="Browser for Playwright tests: chrome, firefox, or safari/webkit.",
    )
    parser.addoption(
        "--tidal-persistent-chrome",
        action="store_true",
        default=False,
        help="Run tests in installed Chrome with a persistent user data directory.",
    )
    parser.addoption(
        "--tidal-chrome-user-data-dir",
        action="store",
        default=None,
        help=(
            "User data directory for --tidal-persistent-chrome. "
            "Defaults to .chrome-user-data in the project root."
        ),
    )
    parser.addoption(
        "--tidal-chrome-profile-directory",
        action="store",
        default=None,
        help="Optional Chrome profile directory name, for example 'Profile 3'.",
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
    }

    if browser_name == "webkit":
        context_options["user_agent"] = SAFARI_USER_AGENT
    elif CHROME_USER_AGENT:
        context_options["user_agent"] = CHROME_USER_AGENT

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

    if browser_name == "firefox":
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
def persistent_chrome_context(playwright_instance, browser_name, pytestconfig):
    use_persistent_chrome = (
        pytestconfig.getoption("--tidal-persistent-chrome")
        or env_flag("TIDAL_USE_PERSISTENT_CHROME")
    )
    if browser_name != "chrome" or not use_persistent_chrome:
        yield None
        return

    user_data_dir = Path(
        pytestconfig.getoption("--tidal-chrome-user-data-dir")
        or os.getenv("TIDAL_CHROME_USER_DATA_DIR")
        or DEFAULT_CHROME_USER_DATA_DIR
    )
    profile_directory = (
        pytestconfig.getoption("--tidal-chrome-profile-directory")
        or os.getenv("TIDAL_CHROME_PROFILE_DIRECTORY")
    )

    print(f"TIDAL tests browser: installed chrome profile {user_data_dir}")
    launch_args = list(CHROME_LAUNCH_ARGS)
    if profile_directory:
        launch_args.append(f"--profile-directory={profile_directory}")

    context = playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        headless=False,
        channel="chrome",
        args=launch_args,
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
    elif browser_name == "firefox":
        print("TIDAL tests browser: firefox")
        browser = playwright_instance.firefox.launch(headless=False)
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
