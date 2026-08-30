"""Regression gate for the latest evaluation report."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from src.rag.config import PROJECT_ROOT

MIN_MEAN_RELEVANCY = 0.6
MIN_MEAN_CORRECTNESS = 0.5
LATEST_REPORT_PATH = PROJECT_ROOT / "evals" / "reports" / "latest.json"


def _load_report() -> dict[str, Any] | None:
    if not LATEST_REPORT_PATH.exists():
        print(f"Missing report: {LATEST_REPORT_PATH}")
        return None
    with LATEST_REPORT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("latest report must be a JSON object")
    return data


def main() -> int:
    report = _load_report()
    if report is None:
        return 1

    aggregates = report.get("aggregates")
    if not isinstance(aggregates, dict):
        print("Missing aggregates in latest report")
        return 1

    mean_relevancy = float(aggregates.get("mean_relevancy", 0.0) or 0.0)
    mean_correctness = float(aggregates.get("mean_correctness", 0.0) or 0.0)

    failed: list[str] = []
    if mean_relevancy < MIN_MEAN_RELEVANCY:
        failed.append(
            f"mean_relevancy {mean_relevancy:.3f} below floor {MIN_MEAN_RELEVANCY:.3f}"
        )
    if mean_correctness < MIN_MEAN_CORRECTNESS:
        failed.append(
            f"mean_correctness {mean_correctness:.3f} below floor {MIN_MEAN_CORRECTNESS:.3f}"
        )

    if failed:
        for item in failed:
            print(item)
        return 1

    print(f"PASS mean_relevancy={mean_relevancy:.3f} mean_correctness={mean_correctness:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
