from __future__ import annotations

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from pathlib import Path
import hashlib
import hmac
import os
import time

from src.rag.config import RETRIEVER_TOP_K, CHUNK_SIZE, CHUNK_OVERLAP
from src.rag.ingest import build_tenant_index
from src.rag.tenant_context import tenant_corpus_dir, use_tenant
from src.rag.strategies import run_strategy
from src.rag.observability import trace_run
from src.rag.models import ALLOWED_MODELS, DEFAULT_MODEL
from src.rag.analytics import log_analytics, read_analytics
from src.rag.live_eval import evaluate_answer
import auth

ALLOWED_STRATEGIES = ["adaptive", "corrective", "cache", "autonomous", "multi_agent"]
DEFAULT_STRATEGY = "adaptive"

DEEPSEEK_CHAT_USD_PER_1M_TOKENS_ESTIMATED = 0.27
OPENAI_TEXT_EMBEDDING_3_SMALL_USD_PER_1M_TOKENS_ESTIMATED = 0.02

_INSECURE_DEFAULT_SECRET = "dev-insecure-session-secret-change-me"
_session_secret = os.environ.get("TESSERA_SESSION_SECRET")
_tessera_env = os.environ.get("TESSERA_ENV", "dev")

if _tessera_env == "prod" and (not _session_secret or _session_secret == _INSECURE_DEFAULT_SECRET):
    raise RuntimeError(
        "TESSERA_ENV is prod but TESSERA_SESSION_SECRET is missing or set to the insecure default. "
        "Set TESSERA_SESSION_SECRET to a strong random value."
    )

SESSION_SECRET = _session_secret or _INSECURE_DEFAULT_SECRET

# OAuth2 password flow. auto_error=False so the existing Authorization-header path still runs
# when no OAuth2 token is presented. This scheme also teaches the interactive docs where the
# token endpoint is, enabling the "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def _make_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time())}"
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_token(token: str) -> int | None:
    try:
        payload, sig = token.rsplit(":", 1)
        user_id_str, _issued_ts = payload.split(":", 1)
        expected_sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return None
        return int(user_id_str)
    except (ValueError, TypeError, AttributeError):
        return None


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    authorization: str | None = Header(default=None),
) -> tuple[int, str]:
    if not token:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
            )
        token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )

    user_id = _verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
        )

    email = auth.get_user_email(user_id)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
        )

    return user_id, email


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str
    is_admin: bool


class AskRequest(BaseModel):
    question: str
    strategy: str | None = None
    model: str | None = None
    top_k: int | None = None
    run_eval: bool = False
    expected_output: str | None = None
    force_route: str | None = None


class AskResponse(BaseModel):
    answer: str
    route: str
    strategy: str
    model: str
    sources: list[str]
    latency_ms: float
    tokens: dict[str, int]
    estimated_cost_usd: float
    tenant: str
    eval: dict | None = None
    trace: list[str]


app = FastAPI(title="Tessera Multi-Tenant RAG API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def config() -> dict:
    return {
        "strategies": ALLOWED_STRATEGIES,
        "default_strategy": DEFAULT_STRATEGY,
        "models": ALLOWED_MODELS,
        "default_model": DEFAULT_MODEL,
        "default_top_k": RETRIEVER_TOP_K,
        "default_chunk_size": CHUNK_SIZE,
        "default_chunk_overlap": CHUNK_OVERLAP,
    }


@app.get("/budget")
def budget() -> dict:
    from src.rag.llm import MAX_OUTPUT_TOKENS, DAILY_SPEND_USD_CAP, spend_so_far

    spent = spend_so_far()
    remaining = max(0.0, DAILY_SPEND_USD_CAP - spent) if DAILY_SPEND_USD_CAP > 0 else None

    return {
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "daily_spend_usd_cap": DAILY_SPEND_USD_CAP,
        "spend_so_far_usd": spent,
        "spend_remaining_usd": remaining,
    }


@app.post("/auth/signup")
def signup(payload: SignupRequest) -> dict[str, str]:
    ok, msg = auth.create_user(payload.email, payload.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"message": msg}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    ok, msg, user_id = auth.authenticate_user(payload.email, payload.password)
    if not ok or user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)
    token = _make_token(user_id)
    return LoginResponse(
        token=token,
        email=payload.email,
        is_admin=auth.is_admin(payload.email),
    )


@app.post("/token")
def issue_oauth2_token(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    ok, msg, user_id = auth.authenticate_user(form_data.username, form_data.password)
    if not ok or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = _make_token(user_id)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    chunk_size: int = Form(CHUNK_SIZE),
    chunk_overlap: int = Form(CHUNK_OVERLAP),
    user: tuple[int, str] = Depends(get_current_user),
) -> dict:
    tenant = auth.tenant_slug(user[0])
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only .md and .txt files are accepted")

    corpus_dir = tenant_corpus_dir(tenant)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    target_path = corpus_dir / filename
    content = await file.read()
    target_path.write_bytes(content)

    result = build_tenant_index(tenant, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return {
        "filename": filename,
        "docs": result["docs"],
        "chunks": result["chunks"],
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "tenant": tenant,
    }


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, user: tuple[int, str] = Depends(get_current_user)) -> AskResponse:
    user_id, email = user
    tenant = auth.tenant_slug(user_id)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question must not be empty")
    if len(question) > 4000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question too long (max 4000 characters)")

    lowered_question = question.lower()
    blocked_phrases = [
        "ignore previous instructions",
        "disregard previous instructions",
        "reveal your system prompt",
        "print your api key",
        "show me your api key",
    ]
    if any(phrase in lowered_question for phrase in blocked_phrases):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="request blocked by input guard")

    strategy = payload.strategy or DEFAULT_STRATEGY
    if strategy not in ALLOWED_STRATEGIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown strategy: {strategy}")

    model = payload.model or DEFAULT_MODEL
    if model not in ALLOWED_MODELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown model: {model}")

    top_k = payload.top_k if payload.top_k else RETRIEVER_TOP_K

    allowed = {"auto", "vector", "web", "direct"}
    fr = payload.force_route or "auto"
    if fr not in allowed:
        fr = "auto"

    start = time.perf_counter()
    with trace_run(strategy, payload.question, tenant) as run_span:
        with use_tenant(tenant):
            result = run_strategy(strategy, payload.question, top_k=top_k, model=model, force_route=fr)
        latency_ms = (time.perf_counter() - start) * 1000
        run_span.finish(
            route=result.get("route", ""),
            answer=result.get("answer", ""),
            latency_ms=latency_ms,
        )

    usage = result.get("usage") or {"prompt": 0, "completion": 0, "total": 0}
    tokens = {
        "prompt": int(usage.get("prompt", 0) or 0),
        "completion": int(usage.get("completion", 0) or 0),
        "total": int(usage.get("total", 0) or 0),
    }
    token_sum = tokens["prompt"] + tokens["completion"]
    estimated_cost_usd = (token_sum / 1_000_000) * DEEPSEEK_CHAT_USD_PER_1M_TOKENS_ESTIMATED

    eval_result = None
    if payload.run_eval:
        try:
            eval_result = evaluate_answer(
                payload.question,
                result.get("answer", ""),
                result.get("contexts", []) or [],
                expected_output=payload.expected_output,
            )
        except Exception:
            eval_result = {"enabled": False, "reason": "eval error"}

    try:
        auth.log_query(
            user_id,
            payload.question,
            result.get("answer", ""),
            result.get("route", ""),
            int(tokens.get("total", 0) or 0),
            estimated_cost_usd,
        )
    except Exception:
        pass

    try:
        log_analytics({
            "timestamp": int(time.time()),
            "user_id": user_id,
            "email": email,
            "tenant": tenant,
            "question": payload.question,
            "answer": result.get("answer", ""),
            "route": result.get("route", ""),
            "strategy": strategy,
            "model": model,
            "top_k": top_k,
            "tokens": tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "latency_ms": latency_ms,
            "eval": eval_result,
            "trace": result.get("trace", []) or [],
        })
    except Exception:
        pass

    return AskResponse(
        answer=result.get("answer", ""),
        route=result.get("route", ""),
        strategy=result.get("strategy", strategy),
        model=model,
        sources=result.get("sources", []) or [],
        latency_ms=latency_ms,
        tokens=tokens,
        estimated_cost_usd=estimated_cost_usd,
        tenant=tenant,
        eval=eval_result,
        trace=result.get("trace", []) or [],
    )


@app.get("/admin/analytics")
def admin_analytics(limit: int = 100, user: tuple[int, str] = Depends(get_current_user)) -> dict:
    if not auth.is_admin(user[1]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return {"records": read_analytics(limit)}