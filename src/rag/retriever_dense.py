"""Dense retrieval over the persisted Chroma index."""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .config import EMBEDDING_MODEL, RETRIEVER_TOP_K, get_openai_api_key
from .tenant_context import active_index_dir


def get_vectorstore() -> Chroma:
    get_openai_api_key()
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return Chroma(persist_directory=str(active_index_dir()), embedding_function=embeddings)


def retrieve(question: str, top_k: int = RETRIEVER_TOP_K):
    vectorstore = get_vectorstore()
    return vectorstore.similarity_search(question, k=top_k)
