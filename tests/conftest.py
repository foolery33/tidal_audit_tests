import random
import time
import pytest
from playwright.sync_api import sync_playwright


def warm_up(page):
    time.sleep(random.uniform(3.0, 5.0))

    for scroll_to in [300, 600, 900, 600, 300, 0]:
        page.evaluate(f"window.scrollTo({{top: {scroll_to}, behavior: 'smooth'}})")
        time.sleep(random.uniform(0.5, 1.2))

    time.sleep(random.uniform(2.0, 3.0))


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            locale="en-US",
            viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)

        page = context.new_page()
        page.goto("https://tidal.com")
        # warm_up(page)

        yield page

        context.close()
        browser.close()