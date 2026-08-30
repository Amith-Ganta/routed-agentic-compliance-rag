"""Answer using only retrieved context."""

from __future__ import annotations

import json

from litellm import completion

from .config import CHAT_MODEL, get_deepseek_api_key


def generate_answer(question: str, contexts: list) -> str:
    context_text = "\n\n".join(doc.page_content for doc in contexts)
    messages = [
        {
            "role": "system",
            "content": "Answer only from the provided context. If the context is insufficient, say you do not know.",
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nContext:\n{context_text}",
        },
    ]
    response = completion(
        model=CHAT_MODEL,
        messages=messages,
        api_key=get_deepseek_api_key(),
        temperature=0,
    )
    return response.choices[0].message.content or ""
