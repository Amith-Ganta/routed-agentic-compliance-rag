from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.rag.agent_pipeline import invoke as agent_invoke
from src.rag.config import RETRIEVER_TOP_K
from src.rag.ingest import build_tenant_index
from src.rag.tenant_context import tenant_corpus_dir, use_tenant

DEEPSEEK_CHAT_USD_PER_1M_TOKENS_ESTIMATED = 0.27
OPENAI_TEXT_EMBEDDING_3_SMALL_USD_PER_1M_TOKENS_ESTIMATED = 0.02

app = FastAPI()


def _tenant_token_map() -> dict[str, str]:
    raw = os.getenv("TENANT_TOKENS")
    if raw:
        mapping: dict[str, str] = {}
        for item in raw.split(","):
            if ":" not in item:
                continue
            token, tenant_id = item.split(":", 1)
            token = token.strip()
            tenant_id = tenant_id.strip()
            if token and tenant_id:
                mapping[token] = tenant_id
        if mapping:
            return mapping
    return {"dev-token-a": "tenant-a", "dev-token-b": "tenant-b"}


def get_tenant_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    tenant_id = _tenant_token_map().get(token)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown token")
    return tenant_id


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


class AskResponse(BaseModel):
    answer: str
    route: str
    sources: list[str]
    latency_ms: float
    tokens: dict[str, int]
    estimated_cost_usd: float
    tenant: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload")
def upload(file: UploadFile = File(...), tenant_id: str = Depends(get_tenant_id)) -> dict[str, object]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only .md and .txt files are accepted")
    corpus_dir = tenant_corpus_dir(tenant_id)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    target = corpus_dir / Path(file.filename).name
    content = file.file.read()
    target.write_bytes(content)
    ingest_result = build_tenant_index(tenant_id)
    return {"filename": target.name, "docs": ingest_result["docs"], "chunks": ingest_result["chunks"], "tenant": tenant_id}


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, tenant_id: str = Depends(get_tenant_id)) -> AskResponse:
    top_k = body.top_k if body.top_k is not None else RETRIEVER_TOP_K
    start = time.perf_counter()
    with use_tenant(tenant_id):
        result = agent_invoke(body.question, top_k=top_k)
    latency_ms = (time.perf_counter() - start) * 1000.0
    tokens = dict(result.get("usage", {"prompt": 0, "completion": 0, "total": 0}))
    prompt_tokens = int(tokens.get("prompt", 0) or 0)
    completion_tokens = int(tokens.get("completion", 0) or 0)
    estimated_cost = ((prompt_tokens + completion_tokens) / 1_000_000.0) * DEEPSEEK_CHAT_USD_PER_1M_TOKENS_ESTIMATED
    return AskResponse(
        answer=str(result.get("answer", "")),
        route=str(result.get("route", "")),
        sources=list(result.get("sources", [])),
        latency_ms=latency_ms,
        tokens=tokens,
        estimated_cost_usd=estimated_cost,
        tenant=tenant_id,
    )
