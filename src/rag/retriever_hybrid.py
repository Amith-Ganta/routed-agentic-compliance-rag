"""Hybrid dense plus sparse retrieval with reciprocal rank fusion."""

from __future__ import annotations

from langchain_core.documents import Document

from .retriever_dense import retrieve as retrieve_dense
from .retriever_sparse import retrieve_sparse


def _dedupe_key(doc: Document) -> tuple[str, str]:
    source = str(doc.metadata.get("source", ""))
    return source, doc.page_content.strip()


def _rrf_rank(score: int, k_constant: int) -> float:
    return 1.0 / (k_constant + score)


def retrieve_hybrid(question: str, top_k: int, rrf_k: int = 60) -> list[Document]:
    """Fuse dense and sparse retrieval results with Reciprocal Rank Fusion."""

    dense_docs = retrieve_dense(question, top_k=top_k)
    sparse_docs = retrieve_sparse(question, top_k=top_k)
    fused: dict[tuple[str, str], dict[str, object]] = {}

    for rank, doc in enumerate(dense_docs, start=1):
        key = _dedupe_key(doc)
        item = fused.setdefault(key, {"doc": doc, "score": 0.0})
        item["score"] = float(item["score"]) + _rrf_rank(rank, rrf_k)

    for rank, doc in enumerate(sparse_docs, start=1):
        key = _dedupe_key(doc)
        item = fused.setdefault(key, {"doc": doc, "score": 0.0})
        item["score"] = float(item["score"]) + _rrf_rank(rank, rrf_k)

    ranked = sorted(fused.values(), key=lambda item: float(item["score"]), reverse=True)
    return [item["doc"] for item in ranked[:top_k]]
