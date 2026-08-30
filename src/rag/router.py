"""Query routing and Tavily fallback retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from litellm import completion
from langchain_core.documents import Document

from .config import CHAT_MODEL, RETRIEVER_TOP_K, get_deepseek_api_key, get_tavily_api_key


@dataclass(frozen=True)
class RoutingDecision:
    route: str
    reason: str


def _safe_parse_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def _classify_once(question: str) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                'Classify the user query as one of "vector", "web", or "direct". '
                'Return strict JSON with keys route and reason.'
            ),
        },
        {"role": "user", "content": question},
    ]
    response = completion(
        model=CHAT_MODEL,
        messages=messages,
        api_key=get_deepseek_api_key(),
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return _safe_parse_json(content)


def route_query(question: str) -> RoutingDecision:
    """Route a question to vector, web, or direct handling."""

    for _ in range(2):
        parsed = _classify_once(question)
        route = str(parsed.get("route", "")).strip().lower()
        reason = str(parsed.get("reason", "")).strip()
        if route in {"vector", "web", "direct"}:
            return RoutingDecision(route=route, reason=reason or "classified by DeepSeek")
    return RoutingDecision(route="vector", reason="fallback after JSON parse failure")


def tavily_search(question: str, top_k: int = RETRIEVER_TOP_K) -> tuple[list[Document], str]:
    """Search Tavily when available, otherwise degrade to an empty result set."""

    try:
        api_key = get_tavily_api_key()
    except RuntimeError:
        return [], "TAVILY_API_KEY missing, degraded to vector fallback"

    payload = json.dumps({"query": question, "max_results": top_k, "search_depth": "advanced"}).encode("utf-8")
    request = Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
    except Exception as exc:
        return [], f"Tavily request failed, degraded to vector fallback: {exc.__class__.__name__}"

    documents: list[Document] = []
    for item in data.get("results", [])[:top_k]:
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        metadata = {
            "source": str(item.get("url", "")),
            "title": str(item.get("title", "")),
        }
        documents.append(Document(page_content=content, metadata=metadata))
    return documents, "Tavily search completed"
