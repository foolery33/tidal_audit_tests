import random
import time
import os
from pathlib import Path

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
CHROME_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
]


def pytest_addoption(parser):
    parser.addoption(
        "--tidal-browser",
        action="store",
        choices=SUPPORTED_BROWSERS,
        default=None,
        help="Browser for Playwright tests: chrome or safari/webkit.",
    )


def warm_up(page):
    time.sleep(random.uniform(3.0, 5.0))

    for scroll_to in [300, 600, 900, 600, 300, 0]:
        page.evaluate(f"window.scrollTo({{top: {scroll_to}, behavior: 'smooth'}})")
        time.sleep(random.uniform(0.5, 1.2))

    time.sleep(random.uniform(2.0, 3.0))


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
        "user_agent": SAFARI_USER_AGENT if browser_name == "webkit" else CHROME_USER_AGENT,
    }

    if use_storage_state and AUTH_STATE_PATH.exists():
        context_options["storage_state"] = str(AUTH_STATE_PATH)

    return context_options


def add_init_scripts(context, browser_name):
    if browser_name == "webkit":
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
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
        page.goto("https://tidal.com", timeout=60000)
        # warm_up(page)

        yield page

        page.close()
        return

    context = playwright_browser.new_context(
        **get_context_options(browser_name),
    )
    add_init_scripts(context, browser_name)

    page = context.new_page()
    page.goto("https://tidal.com", timeout=60000)
    # warm_up(page)

    yield page

    context.close()
