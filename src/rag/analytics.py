from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import PROJECT_ROOT

LOG_DIR: Path = PROJECT_ROOT / "logs"
ANALYTICS_PATH: Path = LOG_DIR / "analytics.jsonl"


def log_analytics(record: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with ANALYTICS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        print("analytics logging failed", file=sys.stderr)


def read_analytics(limit: int = 100) -> list[dict]:
    try:
        if not ANALYTICS_PATH.exists():
            return []
        records: list[dict] = []
        with ANALYTICS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
        if limit <= 0:
            return []
        return records[-limit:][::-1]
    except Exception:
        return []


def clear_analytics() -> None:
    try:
        ANALYTICS_PATH.unlink(missing_ok=True)
    except Exception:
        pass