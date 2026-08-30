"""Bounded LangGraph orchestration for the phase 3 RAG engine."""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agent_pipeline import invoke as engine_invoke


class OrchestratorState(TypedDict, total=False):
    question: str
    answer: str
    route: str
    contexts: list[str]
    sources: list[str]
    turn: int
    max_turns: int
    retries_used: int
    max_retries: int
    tokens: dict[str, int]
    verdict: dict[str, Any]
    history: list[str]


def _empty_tokens() -> dict[str, int]:
    return {"prompt": 0, "completion": 0, "total": 0}


def _add_tokens(base: dict[str, int], extra: dict[str, int]) -> dict[str, int]:
    return {
        "prompt": int(base.get("prompt", 0)) + int(extra.get("prompt", 0)),
        "completion": int(base.get("completion", 0)) + int(extra.get("completion", 0)),
        "total": int(base.get("total", 0)) + int(extra.get("total", 0)),
    }


def _verdict(state: OrchestratorState) -> dict[str, Any]:
    answer = str(state.get("answer", "")).strip()
    contexts = state.get("contexts", [])
    grounded = bool(answer) and bool(contexts)
    return {
        "grounded": grounded,
        "answers_question": bool(answer),
        "feedback": "" if grounded else "answer or contexts missing",
    }


def supervisor(state: OrchestratorState) -> dict[str, Any]:
    turn = int(state.get("turn", 0)) + 1
    max_turns = int(state.get("max_turns", 4))
    max_retries = int(state.get("max_retries", 2))
    verdict = state.get("verdict") or {}
    grounded = bool(verdict.get("grounded", False))
    answers_question = bool(verdict.get("answers_question", False))
    retries_used = int(state.get("retries_used", 0))
    history = list(state.get("history", []))

    if turn >= max_turns:
        next_route: Literal["end", "answer", "refine"] = "end"
    elif turn == 1:
        next_route = "answer"
    elif grounded and answers_question:
        next_route = "end"
    elif retries_used < max_retries:
        next_route = "refine"
    else:
        next_route = "end"

    history.append(f"supervisor:{next_route}")
    return {"turn": turn, "history": history, "route": next_route}


def answer_node(state: OrchestratorState) -> dict[str, Any]:
    result = engine_invoke(str(state.get("question", "")))
    tokens = _add_tokens(state.get("tokens", _empty_tokens()), result.get("usage", _empty_tokens()))
    history = list(state.get("history", []))
    history.append("answer_node")
    return {
        "answer": result.get("answer", ""),
        "route": result.get("route", ""),
        "contexts": list(result.get("contexts", [])),
        "sources": list(result.get("sources", [])),
        "retries_used": int(result.get("retries_used", 0)),
        "tokens": tokens,
        "history": history,
    }


def refine_node(state: OrchestratorState) -> dict[str, Any]:
    retries_used = int(state.get("retries_used", 0)) + 1
    time.sleep(min((2**retries_used) * 0.1, 2.0))
    result = engine_invoke(str(state.get("question", "")))
    tokens = _add_tokens(state.get("tokens", _empty_tokens()), result.get("usage", _empty_tokens()))
    history = list(state.get("history", []))
    history.append("refine_node")
    return {
        "answer": result.get("answer", ""),
        "route": result.get("route", ""),
        "contexts": list(result.get("contexts", [])),
        "sources": list(result.get("sources", [])),
        "retries_used": retries_used,
        "tokens": tokens,
        "history": history,
    }


def check_node(state: OrchestratorState) -> dict[str, Any]:
    verdict = _verdict(state)
    history = list(state.get("history", []))
    history.append("check_node")
    return {"verdict": verdict, "history": history}


def _route_from_supervisor(state: OrchestratorState) -> str:
    return str(state.get("route", "end"))


def build_graph():
    builder = StateGraph(OrchestratorState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("answer_node", answer_node)
    builder.add_node("refine_node", refine_node)
    builder.add_node("check_node", check_node)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "answer": "answer_node",
            "refine": "refine_node",
            "end": END,
        },
    )
    builder.add_edge("answer_node", "check_node")
    builder.add_edge("refine_node", "check_node")
    builder.add_edge("check_node", "supervisor")
    return builder


def run(question: str, thread_id: str = "default", max_turns: int = 4, max_retries: int = 2) -> dict[str, Any]:
    graph = build_graph().compile(checkpointer=MemorySaver())
    initial_state: OrchestratorState = {
        "question": question,
        "answer": "",
        "route": "",
        "contexts": [],
        "sources": [],
        "turn": 0,
        "max_turns": max_turns,
        "retries_used": 0,
        "max_retries": max_retries,
        "tokens": _empty_tokens(),
        "verdict": {"grounded": False, "answers_question": False, "feedback": ""},
        "history": [],
    }
    result = graph.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})
    return {
        "answer": result.get("answer", ""),
        "route": result.get("route", ""),
        "turns_used": int(result.get("turn", 0)),
        "retries_used": int(result.get("retries_used", 0)),
        "tokens": result.get("tokens", _empty_tokens()),
        "thread_id": thread_id,
        "history": result.get("history", []),
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: uv run python -m src.rag.orchestrator "question" [thread_id]')
    question = sys.argv[1]
    thread_id = sys.argv[2] if len(sys.argv) > 2 else "default"
    result = run(question, thread_id=thread_id)
    print(json.dumps({
        "answer": result["answer"],
        "turns_used": result["turns_used"],
        "retries_used": result["retries_used"],
        "tokens": result["tokens"],
    }))


if __name__ == "__main__":
    main()
