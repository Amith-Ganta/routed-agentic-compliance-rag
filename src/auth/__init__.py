"""Authentication and per-user analytics for the Tessera RAG service.

Exposes the SQLite-backed user store (`auth`) and an optional FastAPI request
logging helper (`api_auth_middleware`).
"""
