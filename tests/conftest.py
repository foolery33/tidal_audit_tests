import pytest
from selenium import webdriver
from selenium.webdriver.safari.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc
import random


@pytest.fixture(scope="session")
def browser():

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--window-size={random.randint(1200, 1920)},{random.randint(800, 1080)}")
    options.add_argument("--lang=en-US,en;q=0.9")

    # Реальный user-agent (обновляй актуальным)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    driver = uc.Chrome(options=options, headless=False)

    # Скрыть webdriver флаг
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = { runtime: {} };
        """
    })

    yield driver

    driver.quit()