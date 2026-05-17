import random
import time
import os
from pathlib import Path
from types import MethodType

import pytest
import requests
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCREEN_SIZE = {"width": 1920, "height": 1080}

# ===========================================================================
# НАСТРОЙКА BITBROWSER ID ПРЯМО В КОДЕ
# ===========================================================================
# Вставь сюда ID своего профиля из BitBrowser.
# Его можно найти в списке профилей в одноименной колонке "ID".
BITBROWSER_PROFILE_ID_DEFAULT = "d115da897ceb413ea47670825e98bcd1"

# Дефолтный порт локального API BitBrowser (можно проверить в Settings -> API Settings)
BITBROWSER_API_PORT = os.getenv("BITBROWSER_API_PORT", "54345")
BITBROWSER_API_URL = f"http://127.0.0.1:{BITBROWSER_API_PORT}"


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_range(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        min_value, max_value = [float(part.strip()) for part in value.split(",", 1)]
    except ValueError:
        return default
    if min_value < 0 or max_value < min_value:
        return default
    return min_value, max_value


# Настройки эмуляции поведения человека (сохранены из твоей сборки)
HUMAN_BEHAVIOR_ENABLED = env_flag("TIDAL_HUMAN_BEHAVIOR", True)
PAGE_LOAD_DELAY_RANGE = env_range("TIDAL_PAGE_LOAD_DELAY", (5.0, 10.0))
ACTION_DELAY_RANGE = env_range("TIDAL_ACTION_DELAY", (1.0, 3.0))
INTER_TEST_DELAY_RANGE = env_range("TIDAL_INTER_TEST_DELAY", (8.0, 18.0))
SCROLL_STEP_RANGE = (180, 520)
MOUSE_MOVE_STEP_RANGE = (8, 18)


def pytest_addoption(parser):
    parser.addoption(
        "--bitbrowser-id",
        action="store",
        default=None,
        help="ID профиля BitBrowser для запуска тестов.",
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
        human_pause(1.2, 3.0)
        move_mouse_like_user(self)
        if random.random() < 0.75:
            scroll_like_user(self)
        return response

    page.goto = MethodType(goto_with_human_delay, page)


@pytest.fixture(autouse=True)
def inter_test_delay():
    """Пауза между тестами для имитации реального пользователя."""
    yield
    time.sleep(random.uniform(*INTER_TEST_DELAY_RANGE))


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def browser(playwright_instance, pytestconfig):
    # Приоритет выбора ID: флаг --bitbrowser-id -> ENV -> дефолт из кода
    profile_id = (
            pytestconfig.getoption("--bitbrowser-id")
            or os.getenv("BITBROWSER_PROFILE_ID")
            or BITBROWSER_PROFILE_ID_DEFAULT
    )

    if profile_id:
        profile_id = profile_id.strip()

    if not profile_id or profile_id == "ЗДЕСЬ_ТВОЙ_BITBROWSER_ID":
        raise pytest.UsageError(
            "ID профиля BitBrowser не указан! Пропишите его в переменную BITBROWSER_PROFILE_ID_DEFAULT "
            "внутри conftest.py, либо передайте через флаг --bitbrowser-id=ID"
        )

    print(f"\n[BitBrowser] Отправка запроса на запуск профиля: {profile_id}")
    try:
        res = requests.post(
            f"{BITBROWSER_API_URL}/browser/open",
            json={"id": profile_id},
            timeout=50
        )
        res_data = res.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Не удалось связаться с BitBrowser на порту {BITBROWSER_API_PORT}. "
            f"Убедитесь, что программа BitBrowser запущена. Ошибка: {e}"
        )

    if not res_data.get("success"):
        raise RuntimeError(f"BitBrowser вернул ошибку при старте профиля: {res_data}")

    cdp_endpoint = None
    data_field = res_data.get("data")

    if isinstance(data_field, dict):
        ws_field = data_field.get("ws")
        # Если ws уже является готовой строкой-эндпоинтом (актуальная версия BitBrowser)
        if isinstance(ws_field, str):
            cdp_endpoint = ws_field
        # Если ws возвращается объектом, где внутри лежит selenium
        elif isinstance(ws_field, dict):
            cdp_endpoint = ws_field.get("selenium")
    elif isinstance(data_field, str):
        # В некоторых конфигурациях эндпоинт может прийти прямо в строке data
        if data_field.startswith("ws://"):
            cdp_endpoint = data_field
        else:
            raise RuntimeError(f"BitBrowser вернул непредвиденный текст в 'data': {data_field}")

    if not cdp_endpoint:
        raise RuntimeError(f"Не удалось извлечь CDP-ссылку из ответа BitBrowser. Ответ API: {res_data}")

    print(f"[BitBrowser] Подключаемся через CDP к: {cdp_endpoint}")

    browser_instance = None
    try:
        browser_instance = playwright_instance.chromium.connect_over_cdp(cdp_endpoint)

        context = browser_instance.contexts[0] if browser_instance.contexts else browser_instance.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        install_humanized_goto(page)

        time.sleep(random.uniform(1.5, 3.0))
        page.goto("https://tidal.com", timeout=60000)
        time.sleep(random.uniform(2.0, 4.0))
        warm_up(page)

        yield page

    finally:
        if browser_instance:
            try:
                browser_instance.close()
            except Exception:
                pass

        print(f"[BitBrowser] Запрос на закрытие и синхронизацию профиля: {profile_id}")
        try:
            requests.post(f"{BITBROWSER_API_URL}/browser/close", json={"id": profile_id}, timeout=20)
        except Exception as e:
            print(f"[BitBrowser] Предупреждение при остановке профиля через API: {e}")