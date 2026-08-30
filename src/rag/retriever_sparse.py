"""Sparse BM25 retrieval over the same chunked corpus as the dense index."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .tenant_context import active_corpus_dir


def _tokenize(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


def _load_source_documents(corpus_dir: str) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(Path(corpus_dir).glob("*.md")):
        documents.extend(TextLoader(str(path), encoding="utf-8").load())
    return documents


def _chunk_documents(corpus_dir: str) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return splitter.split_documents(_load_source_documents(corpus_dir))


@lru_cache(maxsize=8)
def _build_bm25(corpus_dir: str) -> tuple[BM25Okapi, list[Document], list[list[str]]]:
    docs = _chunk_documents(corpus_dir)
    tokenized = [_tokenize(doc.page_content) for doc in docs]
    return BM25Okapi(tokenized), docs, tokenized


def retrieve_sparse(question: str, top_k: int) -> list[Document]:
    """Return BM25-ranked documents with the same shape as dense retrieval."""

    bm25, docs, _ = _build_bm25(str(active_corpus_dir()))
    scores = bm25.get_scores(_tokenize(question))
    ranked_indices = sorted(range(len(docs)), key=lambda index: scores[index], reverse=True)[:top_k]
    results: list[Document] = []
    for index in ranked_indices:
        doc = docs[index]
        metadata = dict(doc.metadata)
        metadata.setdefault("source", metadata.get("source", ""))
        results.append(Document(page_content=doc.page_content, metadata=metadata))
    return results
