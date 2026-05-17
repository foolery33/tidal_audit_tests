import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tests.helpers import PROJECT_ROOT, is_tidal_domain
from tests.non_functional_lighthouse.lighthouse_runner import run_lighthouse as run_lighthouse_in_bitbrowser


KEY_PAGES = [
    {
        "name": "главная страница",
        "slug": "home_page",
        "url": "https://tidal.com/",
        "expected_path": "/",
        "expected_query_params": None,
    },
    {
        "name": "страница результатов поиска",
        "slug": "search_results",
        "url": "https://tidal.com/search?q=lola%20young",
        "expected_path": "/search",
        "expected_query_params": {"q": ["lola young"]},
    },
    {
        "name": "страница трека",
        "slug": "track_page",
        "url": "https://tidal.com/album/369342737/track/369342742",
        "expected_path": "/album/369342737/track/369342742",
        "expected_query_params": None,
    },
    {
        "name": "страница альбома",
        "slug": "album_page",
        "url": "https://tidal.com/album/432708332",
        "expected_path": "/album/432708332",
        "expected_query_params": None,
    },
    {
        "name": "страница исполнителя",
        "slug": "artist_page",
        "url": "https://tidal.com/artist/30416609",
        "expected_path": "/artist/30416609",
        "expected_query_params": None,
    },
]

REPORT_DIR = PROJECT_ROOT / "artifacts" / "lighthouse"

MIN_BEST_PRACTICES_SCORE = 0.60
LIGHTHOUSE_FATAL_EXIT_CODES = {2}
LIGHTHOUSE_ENVIRONMENT_ERRORS = [
    "Launching Chrome on Mac Silicon (arm64) from an x64 Node installation",
]

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
    return run_lighthouse_in_bitbrowser(url, report_path, "best-practices")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.unlink(missing_ok=True)

    command = [
        *get_lighthouse_command(),
        url,
        "--quiet",
        "--output=json",
        f"--output-path={report_path}",
        "--only-categories=best-practices",
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
        f"Lighthouse не смог проверить страницу по Best Practices. "
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


def assert_expected_page_was_checked(lhr: dict, page: dict, report_path: Path):
    final_url = lhr.get("finalDisplayedUrl") or lhr.get("finalUrl") or lhr.get("requestedUrl")

    assert final_url, (
        f"В Lighthouse-отчете нет финального URL. "
        f"Страница: {page['name']}. "
        f"URL: {page['url']}. "
        f"Отчет: {report_path}"
    )

    parsed_final_url = urlparse(final_url)

    assert is_tidal_domain(final_url), (
        f"Lighthouse проверил не домен TIDAL. "
        f"Страница: {page['name']}. "
        f"URL: {page['url']}. "
        f"Финальный URL: {final_url}. "
        f"Отчет: {report_path}"
    )

    actual_path = parsed_final_url.path.rstrip("/") or "/"
    expected_path = page["expected_path"].rstrip("/") or "/"

    assert actual_path == expected_path, (
        f"Lighthouse проверил неожиданный маршрут. "
        f"Страница: {page['name']}. "
        f"Ожидался маршрут: {page['expected_path']}. "
        f"Финальный URL: {final_url}. "
        f"Отчет: {report_path}"
    )

    expected_query_params = page.get("expected_query_params")

    if expected_query_params:
        actual_query_params = parse_qs(parsed_final_url.query)

        for query_key, expected_value in expected_query_params.items():
            assert actual_query_params.get(query_key) == expected_value, (
                f"Lighthouse проверил страницу с неожиданным query-параметром. "
                f"Страница: {page['name']}. "
                f"Параметр: {query_key}. "
                f"Ожидалось: {expected_value}. "
                f"Фактически: {actual_query_params.get(query_key)}. "
                f"Финальный URL: {final_url}. "
                f"Отчет: {report_path}"
            )


@pytest.mark.parametrize("page", KEY_PAGES, ids=lambda page: page["slug"])
def test_key_pages_have_no_critical_best_practices_violations(page):
    report_path = REPORT_DIR / f"{page['slug']}_best_practices.json"

    lhr = run_lighthouse(page["url"], report_path)

    runtime_error = lhr.get("runtimeError")

    assert runtime_error is None, (
        f"Lighthouse завершил Best Practices-проверку с runtimeError. "
        f"Страница: {page['name']}. "
        f"URL: {page['url']}. "
        f"Ошибка: {runtime_error}. "
        f"Отчет: {report_path}"
    )

    assert_expected_page_was_checked(lhr, page, report_path)

    best_practices_score = lhr.get("categories", {}).get("best-practices", {}).get("score")

    assert best_practices_score is not None, (
        f"В Lighthouse-отчете отсутствует категория best-practices. "
        f"Страница: {page['name']}. "
        f"URL: {page['url']}. "
        f"Отчет: {report_path}"
    )

    assert best_practices_score >= MIN_BEST_PRACTICES_SCORE, (
        f"Страница имеет критически низкую Lighthouse Best Practices-оценку. "
        f"Страница: {page['name']}. "
        f"Минимум: {MIN_BEST_PRACTICES_SCORE:.2f}. "
        f"Фактически: {best_practices_score:.2f}. "
        f"URL: {page['url']}. "
        f"Отчет: {report_path}"
    )

