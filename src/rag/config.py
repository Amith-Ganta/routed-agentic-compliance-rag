"""Single source of configuration for the Project 2 RAG baseline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)


def get_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            f"OPENAI_API_KEY is not set. Expected it in the local .env file at {ENV_FILE}."
        )
    return key


def get_deepseek_api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError(
            f"DEEPSEEK_API_KEY is not set. Expected it in the local .env file at {ENV_FILE}."
        )
    return key


CORPUS_DIR = PROJECT_ROOT / "data" / "corpus"
INDEX_DIR = PROJECT_ROOT / "data" / "index" / "chroma"
GOLDENS_PATH = PROJECT_ROOT / "goldens" / "retriever_goldens.json"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# OpenAI provides embeddings; DeepSeek provides generation and the eval judge.
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "deepseek/deepseek-chat"
RETRIEVER_TOP_K = 5

