"""Run DeepEval on the retriever goldens and write a reproducible report."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from src.rag.agent_pipeline import invoke
from src.rag.config import GOLDENS_PATH, PROJECT_ROOT
from src.rag.judge import DeepSeekJudge

REPORTS_DIR = PROJECT_ROOT / "evals" / "reports"
LATEST_REPORT_PATH = REPORTS_DIR / "latest.json"
RUN_LABEL = "phase3-eval"


def _load_goldens() -> list[dict[str, Any]]:
    with GOLDENS_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("goldens file must contain a list")
    return [item for item in data if isinstance(item, dict)]


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _short_reason(reason: str) -> str:
    text = reason.strip()
    return text if len(text) <= 220 else f"{text[:217]}..."


def main() -> int:
    goldens = _load_goldens()
    judge = DeepSeekJudge()
    relevancy_model_name = judge.get_model_name()
    correctness_model_name = judge.get_model_name()

    case_rows: list[dict[str, Any]] = []
    relevancy_scores: list[float] = []
    correctness_scores: list[float] = []

    for golden in goldens:
        case_id = str(golden.get("id", ""))
        question = str(golden.get("input", ""))
        expected_output = str(golden.get("expected_output", ""))

        result = invoke(question)
        answer = str(result.get("answer", ""))
        contexts_raw = result.get("contexts", [])
        contexts = [str(item) for item in contexts_raw] if isinstance(contexts_raw, list) else []

        test_case = LLMTestCase(
            input=question,
            actual_output=answer,
            expected_output=expected_output,
            retrieval_context=contexts,
        )

        relevancy_metric = AnswerRelevancyMetric(
            threshold=0.7,
            model=judge,
            include_reason=True,
            async_mode=False,
        )
        correctness_metric = GEval(
            name="Correctness",
            criteria=(
                "Determine whether the actual output is factually consistent with and "
                "covers the key facts in the expected output, given the question."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            threshold=0.5,
            model=judge,
        )

        relevancy_score = None
        relevancy_passed = None
        relevancy_reason = ""
        relevancy_error = ""
        try:
            relevancy_metric.measure(test_case)
            relevancy_score = float(relevancy_metric.score or 0.0)
            relevancy_passed = bool(relevancy_metric.is_successful())
            relevancy_reason = _short_reason(relevancy_metric.reason or "")
            relevancy_scores.append(relevancy_score)
        except Exception as exc:  # pragma: no cover - defensive harness behavior
            relevancy_error = str(exc)

        correctness_score = None
        correctness_passed = None
        correctness_reason = ""
        correctness_error = ""
        try:
            correctness_metric.measure(test_case)
            correctness_score = float(correctness_metric.score or 0.0)
            correctness_passed = bool(correctness_metric.is_successful())
            correctness_reason = _short_reason(correctness_metric.reason or "")
            correctness_scores.append(correctness_score)
        except Exception as exc:  # pragma: no cover - defensive harness behavior
            correctness_error = str(exc)

        case_rows.append(
            {
                "id": case_id,
                "source": str(golden.get("source", "")),
                "route": str(result.get("route", "")),
                "retries_used": int(result.get("retries_used", 0) or 0),
                "relevancy_score": relevancy_score,
                "relevancy_passed": relevancy_passed,
                "relevancy_reason": relevancy_reason,
                "relevancy_error": relevancy_error,
                "correctness_score": correctness_score,
                "correctness_passed": correctness_passed,
                "correctness_reason": correctness_reason,
                "correctness_error": correctness_error,
            }
        )

    aggregate_rows = {
        "count": len(case_rows),
        "mean_relevancy": _safe_mean(relevancy_scores),
        "mean_correctness": _safe_mean(correctness_scores),
        "pass_rate_relevancy": (
            sum(1 for row in case_rows if row["relevancy_passed"] is True) / len(case_rows)
            if case_rows
            else 0.0
        ),
        "pass_rate_correctness": (
            sum(1 for row in case_rows if row["correctness_passed"] is True) / len(case_rows)
            if case_rows
            else 0.0
        ),
    }

    print("id   route   relevancy   correctness")
    for row in case_rows:
        relevancy_text = (
            f'{row["relevancy_score"]:.3f}' if isinstance(row["relevancy_score"], float) else "ERR"
        )
        correctness_text = (
            f'{row["correctness_score"]:.3f}' if isinstance(row["correctness_score"], float) else "ERR"
        )
        print(f'{row["id"]:<4} {row["route"]:<7} {relevancy_text:<10} {correctness_text:<11}')

    report = {
        "run": RUN_LABEL,
        "judge_model": judge.get_model_name(),
        "metrics": {
            "answer_relevancy": {
                "threshold": 0.7,
                "model": relevancy_model_name,
            },
            "correctness": {
                "threshold": 0.5,
                "model": correctness_model_name,
            },
        },
        "aggregates": aggregate_rows,
        "cases": case_rows,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with LATEST_REPORT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
