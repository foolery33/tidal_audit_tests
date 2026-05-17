import atexit
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests

from tests.conftest import (
    BITBROWSER_API_PORT,
    BITBROWSER_API_URL,
    BITBROWSER_PROFILE_ID_DEFAULT,
)
from tests.helpers import PROJECT_ROOT


LIGHTHOUSE_FATAL_EXIT_CODES = {2}
LIGHTHOUSE_ENVIRONMENT_ERRORS = [
    "Launching Chrome on Mac Silicon (arm64) from an x64 Node installation",
]
_BITBROWSER_PROFILE_ID = None
_BITBROWSER_DEBUGGING_PORT = None
_BITBROWSER_CLOSE_REGISTERED = False


def get_lighthouse_command() -> list[str]:
    arm_node = Path("/opt/homebrew/bin/node")
    arm_lighthouse_cli = Path("/opt/homebrew/lib/node_modules/lighthouse/cli/index.js")

    if arm_node.exists() and arm_lighthouse_cli.exists():
        return ["arch", "-arm64", str(arm_node), str(arm_lighthouse_cli)]

    lighthouse_bin = os.environ.get("LIGHTHOUSE_BIN")

    if lighthouse_bin:
        return [lighthouse_bin]

    windows_node_bin = Path(r"C:\Program Files\nodejs\node.exe")
    local_lighthouse_cli = PROJECT_ROOT / "node_modules" / "lighthouse" / "cli" / "index.js"

    if windows_node_bin.exists() and local_lighthouse_cli.exists():
        return [str(windows_node_bin), str(local_lighthouse_cli)]

    local_lighthouse_bins = [
        PROJECT_ROOT / "node_modules" / ".bin" / "lighthouse.cmd",
        PROJECT_ROOT / "node_modules" / ".bin" / "lighthouse",
    ]

    for local_lighthouse_bin in local_lighthouse_bins:
        if local_lighthouse_bin.exists():
            return [str(local_lighthouse_bin)]

    lighthouse_bin = shutil.which("lighthouse")

    if lighthouse_bin:
        return [lighthouse_bin]

    pytest.skip(
        "Для Lighthouse-проверок нужен Lighthouse CLI. "
        "Установите lighthouse и добавьте его в PATH или задайте LIGHTHOUSE_BIN."
    )


def get_bitbrowser_profile_id() -> str:
    profile_id = os.getenv("BITBROWSER_PROFILE_ID") or BITBROWSER_PROFILE_ID_DEFAULT
    profile_id = profile_id.strip() if profile_id else ""

    if not profile_id or profile_id == "ЗДЕСЬ_ТВОЙ_BITBROWSER_ID":
        raise pytest.UsageError(
            "ID профиля BitBrowser не указан. Пропишите BITBROWSER_PROFILE_ID_DEFAULT "
            "в tests/conftest.py или задайте BITBROWSER_PROFILE_ID."
        )

    return profile_id


def extract_cdp_endpoint(response_data: dict) -> str:
    data_field = response_data.get("data")

    if isinstance(data_field, dict):
        ws_field = data_field.get("ws")
        if isinstance(ws_field, str):
            return ws_field
        if isinstance(ws_field, dict) and isinstance(ws_field.get("selenium"), str):
            return ws_field["selenium"]

    if isinstance(data_field, str) and data_field.startswith("ws://"):
        return data_field

    raise RuntimeError(
        f"Не удалось извлечь CDP-ссылку из ответа BitBrowser. Ответ API: {response_data}"
    )


def open_bitbrowser_profile(profile_id: str) -> dict:
    last_response_data = None

    for attempt in range(1, 6):
        try:
            response = requests.post(
                f"{BITBROWSER_API_URL}/browser/open",
                json={"id": profile_id},
                timeout=50,
            )
            response_data = response.json()
        except requests.exceptions.RequestException as error:
            raise RuntimeError(
                f"Не удалось связаться с BitBrowser на порту {BITBROWSER_API_PORT}. "
                f"Убедитесь, что программа BitBrowser запущена. Ошибка: {error}"
            )

        if response_data.get("success"):
            return response_data

        last_response_data = response_data
        if "closing" not in str(response_data.get("msg", "")).lower():
            break

        time.sleep(attempt * 1.5)

    raise RuntimeError(f"BitBrowser вернул ошибку при старте профиля: {last_response_data}")


def close_bitbrowser_profile_at_exit():
    global _BITBROWSER_PROFILE_ID

    if not _BITBROWSER_PROFILE_ID:
        return

    print(f"[BitBrowser][Lighthouse] Запрос на закрытие и синхронизацию профиля: {_BITBROWSER_PROFILE_ID}")
    try:
        requests.post(
            f"{BITBROWSER_API_URL}/browser/close",
            json={"id": _BITBROWSER_PROFILE_ID},
            timeout=20,
        )
    except requests.exceptions.RequestException as error:
        print(f"[BitBrowser][Lighthouse] Предупреждение при остановке профиля: {error}")

    _BITBROWSER_PROFILE_ID = None


def get_bitbrowser_debugging_port() -> int:
    global _BITBROWSER_CLOSE_REGISTERED
    global _BITBROWSER_DEBUGGING_PORT
    global _BITBROWSER_PROFILE_ID

    if _BITBROWSER_DEBUGGING_PORT is not None:
        return _BITBROWSER_DEBUGGING_PORT

    profile_id = get_bitbrowser_profile_id()

    print(f"\n[BitBrowser][Lighthouse] Отправка запроса на запуск профиля: {profile_id}")
    response_data = open_bitbrowser_profile(profile_id)
    cdp_endpoint = extract_cdp_endpoint(response_data)
    port = urlparse(cdp_endpoint).port

    if port is None:
        raise RuntimeError(f"Не удалось извлечь порт из CDP-ссылки BitBrowser: {cdp_endpoint}")

    print(f"[BitBrowser][Lighthouse] Lighthouse подключается через CDP port: {port}")

    _BITBROWSER_PROFILE_ID = profile_id
    _BITBROWSER_DEBUGGING_PORT = port

    if not _BITBROWSER_CLOSE_REGISTERED:
        atexit.register(close_bitbrowser_profile_at_exit)
        _BITBROWSER_CLOSE_REGISTERED = True

    return port


def run_lighthouse(url: str, report_path: Path, category: str) -> dict:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.unlink(missing_ok=True)

    port = get_bitbrowser_debugging_port()
    command = [
        *get_lighthouse_command(),
        url,
        "--quiet",
        "--output=json",
        f"--output-path={report_path}",
        f"--only-categories={category}",
        "--preset=desktop",
        "--max-wait-for-load=60000",
        f"--port={port}",
    ]

    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/opt/homebrew/sbin:" + env.get("PATH", "")

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )

    command_output = f"{completed.stdout}\n{completed.stderr}"

    for environment_error in LIGHTHOUSE_ENVIRONMENT_ERRORS:
        if environment_error in command_output:
            pytest.skip(
                "Lighthouse не может быть запущен в текущем окружении: "
                f"{environment_error}. "
                "Установите arm64 Node.js или задайте LIGHTHOUSE_BIN на Lighthouse, "
                "запускаемый через arm64 Node.js."
            )

    assert completed.returncode not in LIGHTHOUSE_FATAL_EXIT_CODES, (
        f"Lighthouse не смог проверить страницу. "
        f"URL: {url}. "
        f"Категория: {category}. "
        f"Код возврата: {completed.returncode}. "
        f"stdout: {completed.stdout[-2000:]!r}. "
        f"stderr: {completed.stderr[-2000:]!r}"
    )

    assert report_path.exists(), (
        f"Lighthouse не создал JSON-отчет для анализа. "
        f"URL: {url}. "
        f"Категория: {category}. "
        f"Код возврата: {completed.returncode}. "
        f"Ожидался файл: {report_path}. "
        f"stdout: {completed.stdout[-2000:]!r}. "
        f"stderr: {completed.stderr[-2000:]!r}"
    )

    with report_path.open(encoding="utf-8") as report_file:
        return json.load(report_file)
