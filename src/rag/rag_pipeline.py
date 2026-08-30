"""Dense-only RAG pipeline entry point."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .generator import generate_answer
from .retriever_dense import retrieve


@dataclass
class RAGResult:
    answer: str
    contexts: list[str]
    sources: list[str]


def invoke(question: str) -> dict:
    docs = retrieve(question)
    answer = generate_answer(question, docs)
    return {
        "answer": answer,
        "contexts": [doc.page_content for doc in docs],
        "sources": [doc.metadata.get("source", "") for doc in docs],
    }


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: uv run python -m src.rag.rag_pipeline \"question\"")
    result = invoke(sys.argv[1])
    print(result["answer"])
    print("\nSources:")
    for source in result["sources"]:
        print(source)


if __name__ == "__main__":
    main()

