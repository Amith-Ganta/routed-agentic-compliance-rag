from __future__ import annotations

MODEL_REGISTRY: dict[str, dict[str, str]] = {
    "deepseek-chat": {"litellm_id": "deepseek/deepseek-chat", "provider": "deepseek"},
    "gpt-4o-mini": {"litellm_id": "openai/gpt-4o-mini", "provider": "openai"},
    "gpt-4o": {"litellm_id": "openai/gpt-4o", "provider": "openai"},
}

DEFAULT_MODEL = "deepseek-chat"
ALLOWED_MODELS: list[str] = list(MODEL_REGISTRY.keys())


def _validate_name(name: str) -> str:
    if not name or name not in MODEL_REGISTRY:
        allowed = ", ".join(sorted(MODEL_REGISTRY))
        raise ValueError(f"Unknown model {name!r}. Allowed models: {allowed}")
    return name


def resolve_model(name: str) -> tuple[str, str]:
    name = _validate_name(name)
    entry = MODEL_REGISTRY[name]
    litellm_id = entry["litellm_id"]
    provider = entry["provider"]

    # Lazy import avoids loading API keys at module import time.
    from src.rag.config import get_deepseek_api_key, get_openai_api_key

    if provider == "deepseek":
        api_key = get_deepseek_api_key()
    elif provider == "openai":
        api_key = get_openai_api_key()
    else:
        raise ValueError(f"Unsupported provider {provider!r} for model {name!r}")

    return litellm_id, api_key


def provider_for(name: str) -> str:
    name = _validate_name(name)
    return MODEL_REGISTRY[name]["provider"]