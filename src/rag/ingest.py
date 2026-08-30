"""Build and persist the dense index from the local markdown corpus."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CORPUS_DIR, EMBEDDING_MODEL, INDEX_DIR, get_openai_api_key


def load_documents() -> list:
    docs = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        docs.extend(TextLoader(str(path), encoding="utf-8").load())
    return docs


def build_index() -> Chroma:
    # Use OpenAI embeddings for a strong baseline and to mirror Project 1's setup.
    get_openai_api_key()
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents = splitter.split_documents(load_documents())
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma.from_documents(documents=documents, embedding=embeddings, persist_directory=str(INDEX_DIR))


def main() -> None:
    build_index()
    print(f"Built Chroma index at {INDEX_DIR}")


if __name__ == "__main__":
    main()

