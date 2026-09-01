# AI Job Search Project 2

Multi-tenant agentic RAG platform for routing, hybrid retrieval, bounded self-correction, and per-tenant evaluation. The project is being built in phases so every metric, regression gate, and product claim stays traceable to committed scripts and report files.

Status: in progress

## Corpus and domain

The corpus covers cloud compliance and secure platform governance: how regulatory controls such as GDPR, SOC 2, and PCI DSS are enforced on cloud infrastructure through IAM, encryption, audit logging, Kubernetes network policy, secrets management, and infrastructure as code. The text is deliberately dense with exact identifiers (control names, article rights, config flags), which gives the sparse BM25 retriever and the dense retriever genuinely different strengths and makes hybrid fusion worth measuring.

The source documents live in `data/corpus/` and the retriever goldens in `goldens/retriever_goldens.json`. Each golden's `context` field is a sentence copied verbatim from its source file, so the evaluation measures grounding against real corpus text rather than paraphrase.

The dense index is not committed. Rebuild it from the corpus with `uv run python -m src.rag.ingest` before running the app or the eval harness. This step needs a live `OPENAI_API_KEY` because it calls the embedding model.

## Results

Measured over the 12 retriever goldens in `goldens/retriever_goldens.json` by
`evals/run_eval.py`. Every number below is copied from the committed report
`evals/reports/latest.json`, which the harness writes on each run. Judge model:
`deepseek/deepseek-chat` through LiteLLM, wrapped as a custom `DeepEvalBaseLLM`.

| Metric | Value (12 cases) |
| --- | --- |
| Mean answer relevancy | 0.986 |
| Mean correctness (GEval) | 0.858 |
| Answer relevancy pass rate (threshold 0.7) | 100.0% |
| Correctness pass rate (threshold 0.5) | 100.0% |

The regression gate `evals/gate.py` reads the same report and enforces floors
of 0.6 mean relevancy and 0.5 mean correctness. On this run it printed
`PASS mean_relevancy=0.986 mean_correctness=0.858` and exited zero.

Honest reading of this run. The goldens are a small, self-authored set (12
cases) written by the same author as the pipeline, so this shows the pipeline
answers these compliance questions correctly and relevantly, not a general
guarantee. On this run the router classified all 12 questions to the web route
rather than local vector retrieval, so these scores exercise the routing,
generation, self-correction, and judging path end to end, but do not on their
own measure the local hybrid retriever over the corpus. A golden set that the
router sends to the vector route would be needed to score dense, sparse, and
fusion retrieval independently.

To reproduce:

```
uv run python -m src.rag.ingest
uv run python -m evals.run_eval
uv run python -m evals.gate
```

## Evaluation

The evaluation harness measures answer relevancy and correctness with DeepEval over the retriever goldens.

DeepEval is judged by a custom DeepEvalBaseLLM that calls DeepSeek through LiteLLM, so the same local generation stack stays in place for both answering and evaluation.

Run the harness with `uv run python -m evals.run_eval`.

Run the regression gate with `uv run python -m evals.gate`.

The harness writes results to `evals/reports/latest.json`, and no scores are quoted until that file exists.

### Continuous integration

CI runs a lint and compile job, then a merge-blocking eval-gate job.

The eval-gate job runs the DeepEval harness and then the regression gate, and it requires `DEEPSEEK_API_KEY` and `OPENAI_API_KEY` configured as GitHub repository secrets, with `TAVILY_API_KEY` optional.

If those secrets are missing, the gate job fails by design, so a green check always means a real evaluation ran.

## Retrieval engine

Phase 2 adds a routed retrieval layer on top of the existing dense baseline.

- Query routing uses DeepSeek through LiteLLM to choose between local vector retrieval, live web search, or direct answer generation.
- Local retrieval is hybrid, combining the existing dense retriever with a BM25 sparse retriever built over the same chunking configuration.
- Dense and sparse results are fused with Reciprocal Rank Fusion, then reranked with a local cross-encoder before generation.
- Web routes use Tavily when an API key is available, and fall back safely if it is not.
- Generation and self-checking are both handled by DeepSeek, with a bounded retry loop that can revise answers when the judge says the draft is not grounded or incomplete.

This section describes the architecture only. Evaluation metrics will be added later by the eval harness.

## Orchestration

Phase 3 wraps the retrieval engine in a bounded LangGraph state machine
(`src/rag/orchestrator.py`). A rule based supervisor drives two specialist
nodes, an answer node that calls the engine once and a refine node that retries
with exponential backoff, plus a check node that sets a grounding verdict. The
supervisor increments a turn counter on every decision and routes to the end
state once the turn cap is reached, so the graph cannot loop forever by
construction. Per thread checkpointing uses a LangGraph `MemorySaver` keyed on
`thread_id`, and token usage from every DeepSeek call is accumulated into the
run state so each run reports its own cost.

The design targets three acceptance criteria: the graph completes within a
fixed turn cap, retries stay bounded and backed off, and token usage is
captured per run.

One committed run is recorded in `evals/reports/orchestration_run.json`,
produced by `scripts/orchestration_demo.py`. On that run the graph settled in
2 turns with 0 refine retries, following the path
`supervisor -> answer -> check -> supervisor -> end`, and reported 9,270 total
tokens for the run. Because the router sends this question to the live web
route, the exact token count varies between runs while the turn and retry
bounds do not.

To reproduce:

```
uv run python -m scripts.orchestration_demo
uv run python -m src.rag.orchestrator "What does least privilege mean in IAM?"
```

## Tenancy

Phase 4 turns the engine into a multi-tenant product. Each tenant gets its own
physically separate corpus directory and its own persisted Chroma index under
`data/tenants/<id>/corpus` and `data/index/tenants/<id>/chroma`, rather than a
shared store filtered by a metadata field. A `contextvars.ContextVar`
(`src/rag/tenant_context.py`) holds the active tenant, and `use_tenant(id)`
scopes both retrieval paths to that tenant for the duration of a request. With
no tenant active the context resolves to the global directories, so every
existing eval and CLI path behaves exactly as before. Tenant ids are validated
as a strict slug (`[a-z0-9_-]`) so a value like `../etc` is rejected before it
can reach the filesystem. The sparse BM25 cache is keyed on the active corpus
directory, so one tenant's corpus cannot leak into another through a shared
cache slot.

A small FastAPI app (`src/api/app.py`) exposes the product surface: `GET /health`,
`POST /upload` (which stores a `.md` or `.txt` file into the caller's tenant
corpus and rebuilds that tenant index), and `POST /ask` (which answers inside
`use_tenant`, measures latency with `time.perf_counter()`, and reports token
usage plus an estimated cost from clearly labelled per-million-token rate
constants). A bearer token maps each request to a tenant, and an unknown token
is rejected with HTTP 401.

The isolation guarantee is proven deterministically at the retrieval layer,
without spending any LLM tokens. `scripts/tenancy_demo.py` seeds tenant-a with a
document containing `ALPHA_SENTINEL_PHRASE` and tenant-b with a different
sentinel, builds each tenant index with real OpenAI embeddings, then queries for
tenant-a's phrase under each tenant. The committed record in
`evals/reports/tenancy_isolation.json` shows `isolation_holds: true`, with
`a_can_see_a: true` and `b_can_see_a: false`: tenant A retrieves its own
document while tenant B cannot retrieve tenant A's document at all.

To reproduce:

```
uv run python -m scripts.tenancy_demo
uv run uvicorn src.api.app:app --reload
```

## Cost controls, security, and guardrails

### Cost controls

`src/rag/llm.py` enforces two caps:

- `MAX_OUTPUT_TOKENS` (env `TESSERA_MAX_OUTPUT_TOKENS`, default `1024`) caps output tokens per answer.
- `DAILY_SPEND_USD_CAP` (env `TESSERA_DAILY_SPEND_USD_CAP`, default `5.0` USD) is a running per-process spend ceiling. When it is reached, the next model call raises and the request fails closed instead of spending more.

The backend exposes `GET /budget` with no auth, aggregate only. It returns `max_output_tokens`, `daily_spend_usd_cap`, `spend_so_far_usd`, and `spend_remaining_usd`.

The Streamlit sidebar has a "Cost Controls" panel that calls `/budget` and shows the per-answer token cap, the daily spend cap, and the running spend for the current process.

Honest note: `spend_so_far_usd` resets when the API process restarts. It is in-process, not persisted, so it tracks a single run, not lifetime spend.

### Security

Session tokens are signed with `SESSION_SECRET`. In dev the app falls back to a known insecure default so local runs work with no setup. If `TESSERA_ENV=prod` and `TESSERA_SESSION_SECRET` is missing or equal to that insecure default, the app raises `RuntimeError` at import time and refuses to start. This is fail-closed: a misconfigured prod deploy stops rather than running with a guessable signing key.

### Guardrails

`POST /ask` validates the question before running any strategy:

- Empty questions are rejected with HTTP 400.
- Questions over 4000 characters are rejected with HTTP 400.
- A small blocklist of obvious prompt injection and secret-probe phrases is rejected with HTTP 400, for example "ignore previous instructions", "reveal your system prompt", and "print your api key".

This is a lightweight first line of defense, not a complete jailbreak filter.

### Answer-quality evaluation in the UI

The Streamlit answer form has an "Evaluate answer quality (DeepEval)" checkbox and an optional expected-answer text box. When checked, the `/ask` request sets `run_eval=true`, and sets `expected_output` if provided.

The backend runs DeepEval using judge model `gpt-4o-mini` via `OpenAIModel` over the question, answer, and retrieved contexts. It returns the per-metric scores in the response `eval` field. The frontend renders them in a "DeepEval" expander with a pass or fail marker, score, threshold, and the judge's reason per metric.

Requirement: displaying real scores needs a live `OPENAI_API_KEY` in the local `.env`, because the judge is an OpenAI model. Without it, the backend returns eval disabled and the panel shows nothing, by design, rather than crashing.

To run locally:

```
uv run uvicorn src.api.app:app --reload --port 8000
uv run streamlit run app_streamlit_auth.py
```
