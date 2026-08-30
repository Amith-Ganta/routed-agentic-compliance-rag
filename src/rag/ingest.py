"""Build and persist the dense index from the local markdown corpus."""

from __future__ import annotations

from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CORPUS_DIR, EMBEDDING_MODEL, INDEX_DIR, get_openai_api_key
from .tenant_context import tenant_corpus_dir, tenant_index_dir


def load_documents() -> list:
    docs = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        docs.extend(TextLoader(str(path), encoding="utf-8").load())
    return docs


def build_index() -> Chroma:
    # Use OpenAI embeddings for a strong baseline and to mirror Project 1's setup.
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents = splitter.split_documents(load_documents())
    get_openai_api_key()
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma.from_documents(documents=documents, embedding=embeddings, persist_directory=str(INDEX_DIR))


def build_tenant_index(tenant_id: str) -> dict[str, object]:
    corpus_dir = tenant_corpus_dir(tenant_id)
    index_dir = tenant_index_dir(tenant_id)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    docs = []
    for path in sorted(corpus_dir.glob("*.md")):
        docs.extend(TextLoader(str(path), encoding="utf-8").load())

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(docs)
    get_openai_api_key()
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=str(index_dir))
    return {"tenant_id": tenant_id, "docs": len(docs), "chunks": len(chunks), "index_dir": str(index_dir)}


def main() -> None:
    build_index()
    print(f"Built Chroma index at {INDEX_DIR}")


if __name__ == "__main__":
    main()
