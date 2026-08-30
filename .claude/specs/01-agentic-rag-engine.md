# 01 Agentic RAG Engine

## Purpose
Build the core retrieval and answering engine for a multi-tenant agentic RAG platform.

## In scope
- Routing between query paths.
- Hybrid retrieval using BM25, dense vectors, RRF, and reranking.
- A bounded self-correcting answer loop.

## Out of scope
- Full evaluation harness.
- Tenant isolation and product APIs.
- CI regression gates.

## Done when
- Dense and hybrid retrieval paths both work.
- The self-correction loop is bounded and enforced.
- The engine can be invoked without introducing unbounded agent loops.

## Deferred
- Web fallback polish.
- Per-tenant storage separation.
- Production observability and cost accounting.

