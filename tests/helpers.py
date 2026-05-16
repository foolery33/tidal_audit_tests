from pathlib import Path
from urllib.parse import urlparse

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(relative_path: str) -> list[dict]:
    path = PROJECT_ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(f"Не найден файл с тестовыми данными: {path}")

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def is_tidal_domain(url: str) -> bool:
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname or ""

    return hostname == "tidal.com" or hostname.endswith(".tidal.com")