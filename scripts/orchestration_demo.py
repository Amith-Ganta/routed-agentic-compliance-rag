"""Run one bounded orchestration and write a reproducible run record.

This proves the phase 3 supervisor graph terminates within its turn cap,
keeps retries bounded, and captures token usage per run. It writes the result
to evals/reports/orchestration_run.json so the README can quote real numbers
that trace back to a committed script.

Run with the project venv from the project root:

    uv run python -m scripts.orchestration_demo
"""

from __future__ import annotations

import json
from pathlib import Path

from src.rag.config import PROJECT_ROOT
from src.rag.orchestrator import run

QUESTION = "What does least privilege mean in IAM?"
THREAD_ID = "demo-orchestration"
REPORT_PATH = PROJECT_ROOT / "evals" / "reports" / "orchestration_run.json"


def main() -> None:
    result = run(QUESTION, thread_id=THREAD_ID, max_turns=4, max_retries=2)
    record = {
        "run": "phase3-orchestration",
        "question": QUESTION,
        "thread_id": result["thread_id"],
        "turns_used": result["turns_used"],
        "retries_used": result["retries_used"],
        "tokens": result["tokens"],
        "route": result["route"],
        "history": result["history"],
        "answer_chars": len(result["answer"]),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(
        "orchestration run: "
        f"turns_used={record['turns_used']} "
        f"retries_used={record['retries_used']} "
        f"total_tokens={record['tokens']['total']}"
    )
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
