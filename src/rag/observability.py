"""LangSmith observability with a safe no-op fallback.

Tracing is optional. When LANGSMITH_API_KEY (or LANGCHAIN_API_KEY) is present in
the environment, LLM calls and full RAG runs are traced to LangSmith. When it is
absent, or the langsmith package is unavailable, every helper here degrades to a
no-op so the app runs exactly the same with tracing off. Nothing in the request
path depends on a network call to LangSmith succeeding.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

PROJECT = os.getenv("LANGSMITH_PROJECT", "tessera-rag")


def _enabled() -> bool:
    if os.getenv("LANGSMITH_TRACING", "").lower() in {"false", "0", "no"}:
        return False
    return bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))


def _client():
    try:
        from langsmith import Client

        return Client()
    except Exception:
        return None


class _Span:
    """Minimal span. Records a LangSmith run when enabled, else does nothing."""

    def __init__(self, name: str, run_type: str, inputs: dict[str, Any]):
        self._run = None
        self._client = None
        if not _enabled():
            return
        self._client = _client()
        if self._client is None:
            return
        try:
            self._run = self._client.create_run(
                name=name,
                run_type=run_type,
                inputs=inputs,
                project_name=PROJECT,
            )
        except Exception:
            self._run = None

    def finish(self, **outputs: Any) -> None:
        if self._client is None or self._run is None:
            return
        try:
            run_id = getattr(self._run, "id", None) or self._run
            self._client.update_run(run_id, outputs=outputs)
        except Exception:
            pass


@contextlib.contextmanager
def trace_llm(model: str, messages: list[dict[str, str]]):
    span = _Span(
        name=f"llm:{model}",
        run_type="llm",
        inputs={"model": model, "messages": messages[-2:]},
    )
    try:
        yield span
    finally:
        pass


@contextlib.contextmanager
def trace_run(strategy: str, question: str, tenant: str):
    span = _Span(
        name=f"rag:{strategy}",
        run_type="chain",
        inputs={"strategy": strategy, "question": question, "tenant": tenant},
    )
    try:
        yield span
    finally:
        pass
