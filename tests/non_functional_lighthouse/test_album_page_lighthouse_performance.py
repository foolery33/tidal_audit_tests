import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

from tests.helpers import PROJECT_ROOT, is_tidal_domain
from tests.non_functional_lighthouse.lighthouse_runner import run_lighthouse as run_lighthouse_in_bitbrowser


ALBUM_URL = "https://tidal.com/album/432708332"
EXPECTED_ALBUM_PATH = "/album/432708332"

REPORT_PATH = PROJECT_ROOT / "artifacts" / "lighthouse" / "album_page_performance.json"

MIN_PERFORMANCE_SCORE = 0.30
LIGHTHOUSE_FATAL_EXIT_CODES = {2}
LIGHTHOUSE_ENVIRONMENT_ERRORS = [
    "Launching Chrome on Mac Silicon (arm64) from an x64 Node installation",
]

CRITICAL_AUDITS = {
    "first-contentful-paint": "First Contentful Paint",
    "largest-contentful-paint": "Largest Contentful Paint",
    "speed-index": "Speed Index",
    "total-blocking-time": "Total Blocking Time",
    "cumulative-layout-shift": "Cumulative Layout Shift",
}


def get_lighthouse_command() -> list[str]:
    arm_node = Path("/opt/homebrew/bin/node")
    arm_lighthouse_cli = Path("/opt/homebrew/lib/node_modules/lighthouse/cli/index.js")

    if arm_node.exists() and arm_lighthouse_cli.exists():
        return [
            "arch",
            "-arm64",
            str(arm_node),
            str(arm_lighthouse_cli),
        ]

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


def run_lighthouse(url: str, report_path: Path) -> dict:
    return run_lighthouse_in_bitbrowser(url, report_path, "performance")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.unlink(missing_ok=True)

    command = [
        *get_lighthouse_command(),
        url,
        "--quiet",
        "--output=json",
        f"--output-path={report_path}",
        "--only-categories=performance",
        "--preset=desktop",
        "--max-wait-for-load=60000",
        "--chrome-flags=--headless=new --no-sandbox --disable-dev-shm-usage",
    ]

    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/opt/homebrew/sbin:" + env.get("PATH", "")

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
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
        f"Lighthouse не смог проверить страницу альбома. "
        f"URL: {url}. "
        f"Код возврата: {completed.returncode}. "
        f"stdout: {completed.stdout[-2000:]!r}. "
        f"stderr: {completed.stderr[-2000:]!r}"
    )

    assert report_path.exists(), (
        f"Lighthouse не создал JSON-отчет для анализа. "
        f"URL: {url}. "
        f"Код возврата: {completed.returncode}. "
        f"Ожидался файл: {report_path}. "
        f"stdout: {completed.stdout[-2000:]!r}. "
        f"stderr: {completed.stderr[-2000:]!r}"
    )

    with report_path.open(encoding="utf-8") as report_file:
        return json.load(report_file)


def get_audit_score(lhr: dict, audit_id: str) -> float | None:
    audit = lhr.get("audits", {}).get(audit_id, {})

    return audit.get("score")


def test_album_page_passes_basic_lighthouse_performance_check():
    lhr = run_lighthouse(ALBUM_URL, REPORT_PATH)

    runtime_error = lhr.get("runtimeError")

    assert runtime_error is None, (
        f"Lighthouse завершил проверку страницы альбома с runtimeError. "
        f"URL: {ALBUM_URL}. "
        f"Ошибка: {runtime_error}"
    )

    final_url = lhr.get("finalDisplayedUrl") or lhr.get("finalUrl") or lhr.get("requestedUrl")

    assert final_url, (
        f"В Lighthouse-отчете нет финального URL. "
        f"URL: {ALBUM_URL}. "
        f"Отчет: {REPORT_PATH}"
    )

    parsed_final_url = urlparse(final_url)

    assert is_tidal_domain(final_url), (
        f"Lighthouse проверил не домен TIDAL. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {final_url}. "
        f"Отчет: {REPORT_PATH}"
    )

    assert parsed_final_url.path.rstrip("/") == EXPECTED_ALBUM_PATH, (
        f"Lighthouse проверил неожиданный маршрут вместо страницы альбома. "
        f"URL: {ALBUM_URL}. "
        f"Финальный URL: {final_url}. "
        f"Отчет: {REPORT_PATH}"
    )

    performance_score = lhr.get("categories", {}).get("performance", {}).get("score")

    assert performance_score is not None, (
        f"В Lighthouse-отчете отсутствует категория performance. "
        f"URL: {ALBUM_URL}. "
        f"Отчет: {REPORT_PATH}"
    )

    assert performance_score >= MIN_PERFORMANCE_SCORE, (
        f"Страница альбома имеет критически низкую Lighthouse performance-оценку. "
        f"Минимум: {MIN_PERFORMANCE_SCORE:.2f}. "
        f"Фактически: {performance_score:.2f}. "
        f"URL: {ALBUM_URL}. "
        f"Отчет: {REPORT_PATH}"
    )

    failed_critical_audits = [
        f"{audit_name} ({audit_id})"
        for audit_id, audit_name in CRITICAL_AUDITS.items()
        if get_audit_score(lhr, audit_id) == 0
    ]

    assert not failed_critical_audits, (
        f"Страница альбома имеет критические замечания Lighthouse "
        f"по базовым performance-аудитам: {failed_critical_audits}. "
        f"URL: {ALBUM_URL}. "
        f"Performance score: {performance_score:.2f}. "
        f"Отчет: {REPORT_PATH}"
    )
