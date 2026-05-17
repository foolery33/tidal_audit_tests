import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_STATE_PATH = PROJECT_ROOT / ".auth" / "tidal.json"
CHROME_USER_AGENT = os.getenv("TIDAL_CHROME_USER_AGENT")
SAFARI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.0 Safari/605.1.15"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save TIDAL Playwright auth state after a manual login.",
    )
    parser.add_argument(
        "--browser",
        choices=("chrome", "firefox", "safari", "webkit"),
        default="chrome",
        help="Browser engine to use for manual login.",
    )

    return parser.parse_args()


def launch_browser(playwright, browser_name: str):
    if browser_name in {"safari", "webkit"}:
        return playwright.webkit.launch(headless=False)

    if browser_name == "firefox":
        return playwright.firefox.launch(headless=False)

    return playwright.chromium.launch(
        headless=False,
        channel="chrome",
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--start-maximized",
        ],
    )


def main() -> None:
    args = parse_args()

    with sync_playwright() as p:
        browser = launch_browser(p, args.browser)

        context_options = {
            "locale": "en-US",
            "viewport": None,
        }
        if args.browser in {"safari", "webkit"}:
            context_options["user_agent"] = SAFARI_USER_AGENT
        elif args.browser == "chrome" and CHROME_USER_AGENT:
            context_options["user_agent"] = CHROME_USER_AGENT

        context = browser.new_context(**context_options)

        if args.browser == "chrome":
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                if (!window.chrome) {
                    window.chrome = { runtime: {} };
                }
                if (window.navigator.permissions?.query) {
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) =>
                        parameters.name === 'notifications'
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery(parameters);
                }
            """)
        else:
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

        page = context.new_page()
        page.goto("https://tidal.com/login", timeout=60_000)

        input(
            "Log in to TIDAL in the opened browser window, then press Enter here "
            "to save the session..."
        )

        AUTH_STATE_PATH.parent.mkdir(exist_ok=True)
        context.storage_state(path=AUTH_STATE_PATH)

        context.close()
        browser.close()

    print(f"Saved TIDAL auth state to {AUTH_STATE_PATH}")


if __name__ == "__main__":
    main()
