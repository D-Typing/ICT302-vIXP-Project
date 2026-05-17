import os
from pathlib import Path
from typing import Iterable

DEFAULT_VM_ENV = {
    "VM1_HOST": "151.158.219.194",
    "VM2_HOST": "151.158.219.195",
    "VM_USERNAME": "basit00",
    "VM_PASSWORD": "basit00@software@@",
}


def ensure_env_file(base_dir: Path) -> Path:
    env_path = base_dir / ".env"
    if env_path.exists():
        return env_path

    env_path.write_text("\n".join(f"{key}={value}" for key, value in DEFAULT_VM_ENV.items()) + "\n", encoding="utf-8")
    return env_path


def env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError:
        return default


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def filter_records(records: list[dict], query: str, fields: Iterable[str]) -> list[dict]:
    if not query:
        return records

    lowered_query = query.lower()
    filtered: list[dict] = []
    for record in records:
        for field in fields:
            value = str(record.get(field, "")).lower()
            if lowered_query in value:
                filtered.append(record)
                break
    return filtered
