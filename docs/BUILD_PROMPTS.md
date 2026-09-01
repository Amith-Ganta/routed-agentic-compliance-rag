# Project 2 build prompts (agentic RAG platform)

Hand these to the DeepSeek harness or Claude CLI **one phase at a time, in order**. Each
prompt is self-contained: it states the goal, the exact files to touch, the honesty rules,
and a "done when" check. Do not skip ahead; each phase assumes the previous one committed.

Target folder (the CLI must treat this as the repo root):
`AI-JOB-Search-Project-2`

## Non-negotiable rules to paste at the top of EVERY phase

```
HARD RULES (apply to this whole repo, every phase):
1. HONESTY: No number reaches the README, a CV, or any report unless a committed script
   printed it and the raw output sits in a committed file under evals/reports/ (or the
   equivalent results dir). Never hand-type a metric. The CV bullets that inspired this
   project (recall@k +26-31%, hallucination -60%, cost -40-60%, p95 -40%) are TARGETS, not
   facts. Replace each with the real measured value the repo produces, or cut it.
2. SECRETS: Never read, print, echo, log, or commit any API key VALUE. .env is gitignored.
   Ship only .env.example with bare variable NAMES. Confirm .env is not staged before any commit.
3. SCOPE DISCIPLINE: Build exactly the phase you are told to build. Do not pull forward
   later phases. If something is out of scope, note it in the spec's "deferred" list, do not code it.
4. STACK: Python >=3.11, uv package manager, FastAPI for the service, LangGraph for
   orchestration, ChromaDB for dense vectors, rank-bm25 for sparse. Mirror Project 1's layout
   convention: .claude/PROJECT.md, numbered .claude/specs/NN-*.md, src/ package, evals/, scripts/.
5. JUDGE MODEL: Evaluation uses a custom DeepSeek judge over LiteLLM (LiteLLMModel wrapper),
   JSON-mode output, retries with backoff. No OpenAI dependency in the eval path. State the
   judge model and that it needs DEEPSEEK_API_KEY.
6. COMMITS: One clean commit per phase, honest message describing what was built and measured.
   End every commit message with: Co-Authored-By: <your harness/agent tag>.
7. ENGLISH: All docs and comments in plain professional English. No em-dashes in any file.
```

---

## Phase 0 - Scaffold, specs, and honesty guardrails

```
Goal: Stand up an empty but well-structured repo for a multi-tenant agentic RAG platform,
following Project 1's .claude convention, so later phases have a home. NO product logic yet.

Do this:
1. In the repo root, run: git init (core.autocrlf false), uv init, set requires-python >=3.11.
2. Create .gitignore covering: .venv/, .env, __pycache__/, *.pyc, .pytest_cache/, data/index/,
   evals/reports/*.json (with a comment that canonical reports are force-added later), .deepeval/,
   .claude/settings.local.json. Create .env.example with bare names only:
   DEEPSEEK_API_KEY=, OPENAI_API_KEY=, TAVILY_API_KEY=  (values EMPTY).
3. Create .claude/PROJECT.md: one paragraph on what this project is (multi-tenant agentic RAG
   platform: routing + hybrid retrieval + self-correction, a two-level per-tenant eval harness,
   bounded orchestration, and a tenancy/upload/cost-visibility product layer), and the honesty
   rules above restated.
4. Create these spec files (spec text only, NO code), each with: purpose, in-scope, out-of-scope,
   done-when, and a deferred list:
   - .claude/specs/01-agentic-rag-engine.md  (routing, hybrid retrieval BM25+dense+RRF+reranker,
     bounded self-correcting loop)
   - .claude/specs/02-eval-harness.md         (two-level: retriever scored separately from the
     full app; DeepSeek/LiteLLM judge; contextual recall+precision+faithfulness+answer-relevancy;
     G-Eval correctness with decoupled steps; per-run judge cost + retrieval latency captured)
   - .claude/specs/03-orchestration.md        (LangGraph supervisor + bounded specialists,
     per-thread checkpointing, token accounting, retry with backoff, hard turn caps)
   - .claude/specs/04-tenancy-product.md      (auth, isolated per-tenant doc stores, per-tenant
     eval runs, cost/latency surfaced per answer)
5. Write a minimal README.md: title, one-paragraph pitch, "status: in progress", and a
   placeholder "## Results" section that says numbers land here once measured (no fake numbers).
6. Commit: "Scaffold multi-tenant agentic RAG platform: specs and project conventions".

Done when: git status is clean, .env is NOT tracked (git ls-files shows no .env), the four
specs and PROJECT.md exist, and README has an empty honest Results section. Print git ls-files.
```

---

## Phase 1 - Corpus, ingestion, and the plain dense baseline

```
Goal: A working single-tenant RAG baseline (dense retrieval only) over a small self-written
corpus, so later retrieval upgrades have something honest to beat. This is the control.

Do this:
1. data/corpus/: write 10-14 short .md documents on a coherent theme (suggest: agentic RAG,
   hybrid retrieval, RRF, rerankers, query routing, self-correction/CRAG, LangGraph, evaluation,
   multi-tenancy, semantic caching). Your own words. These are the ground truth for evals.
2. src/rag/config.py: load DEEPSEEK_API_KEY / OPENAI_API_KEY from a root .env via python-dotenv.
   Never print values. Define model names and paths in one place.
3. src/rag/ingest.py: load every .md in data/corpus/, chunk, embed (use OpenAI
   text-embedding-3-small OR a local sentence-transformers model - pick one, state which and why
   in a comment), persist a Chroma index to data/index/ (gitignored, rebuildable).
4. src/rag/retriever_dense.py: top-k dense retrieval from Chroma.
5. src/rag/generator.py: answer strictly from retrieved context with a DeepSeek chat model over
   LiteLLM; refuse when context is insufficient.
6. src/rag/pipeline.py: invoke(question) -> {answer, contexts, sources}. Expose a --use flag or
   param later; for now dense-only.
7. scripts/build_index.py and a CLI: `uv run python -m src.rag.pipeline "..."`.
8. goldens/retriever_goldens.json: 12+ entries {id, source, input, expected_output, context},
   each fact traceable to a specific corpus doc. Hand-authored.
9. Commit: "Dense RAG baseline over a self-written corpus with a hand-authored golden set".

Done when: build_index runs, a sample question returns a grounded answer with sources, and the
golden set has >=12 traceable entries. Do NOT report retrieval quality numbers yet (that is Phase 3).
```

---

## Phase 2 - Hybrid retrieval + routing + bounded self-correction

```
Goal: Turn the baseline into the real agentic engine. Everything here must be measurable
against the Phase 1 baseline in Phase 3, so keep the dense-only path intact and switchable.

Do this:
1. src/rag/retriever_sparse.py: BM25 over the same chunks (rank-bm25).
2. src/rag/fusion.py: Reciprocal Rank Fusion (RRF) combining dense + sparse rankings.
3. src/rag/reranker.py: cross-encoder rerank (sentence-transformers cross-encoder/ms-marco-MiniLM-L-6-v2)
   over the fused candidates.
4. src/rag/router.py: an LLM structured-output router that classifies a query into
   {vector, web, direct} with a confidence score; confidence below a threshold falls back to web.
   Web path uses Tavily (guard for missing key: degrade to vector, do not crash).
5. src/rag/self_correct.py: a BOUNDED loop - if the drafted answer is judged ungrounded, regenerate;
   if the query is off-topic for the corpus, route to web. HARD cap (<=2 retries). The bound is a
   feature: state it and enforce it, never loop unbounded.
6. Wire pipeline.invoke to accept mode: dense | hybrid | hybrid+rerank | agentic, so every stage
   is independently benchmarkable. Default: agentic.
7. Commit: "Hybrid retrieval (BM25+dense+RRF+rerank), LLM routing, bounded self-correction".

Done when: pipeline runs in all four modes on the same question without error, the self-correct
loop provably stops at the cap, and the web fallback degrades gracefully with no Tavily key.
Print one example per mode. Still NO quality numbers - that is Phase 3.
```

---

## Phase 3 - Two-level eval harness (the CV-metric engine) [MOST IMPORTANT]

```
Goal: The measurement layer that produces every real number this project is allowed to claim.
Two levels: score the RETRIEVER separately from the full APPLICATION, so a regression traces
cleanly to retrieval vs generation. This mirrors Project 1's proven approach.

Do this:
1. evals/judge.py: a custom DeepSeek judge via LiteLLM (LiteLLMModel), JSON-mode output,
   retries with exponential backoff (<=3). State the judge model. No OpenAI in this path.
2. evals/config.py: judge model name, DEFAULT_THRESHOLD, reports dir, goldens path. UTF-8
   stdout reconfigure (Windows console safety, as in Project 1).
3. evals/eval_retriever.py: for each golden, run retrieval and score ContextualRecall,
   ContextualPrecision, ContextualRelevancy with DeepEval, using the custom judge. Accept a
   --mode flag (dense | hybrid | hybrid+rerank | agentic) so each retrieval stage is scored.
   Also record retrieval LATENCY per query.
4. evals/eval_application.py: end-to-end. Faithfulness, AnswerRelevancy, and a G-Eval
   Correctness metric whose steps are DECOUPLED (brevity must not cost a correct answer its score).
   Record judge token COST per run.
5. Every script writes a timestamped JSON report to evals/reports/ with per-case scores, the
   aggregate mean per metric, latency, and judge cost. Print the aggregate table to stdout.
6. Run each retrieval mode once and the application once. Force-add the canonical reports so
   the evidence ships (git add -f).
7. Write the REAL numbers into README's Results section as a mode-by-mode table
   (dense vs hybrid vs +rerank vs agentic) plus the application table, each citing its exact
   report filename. If a metric did NOT improve, report it honestly - a flat or negative result
   is still a real result and reads as senior.
8. Commit: "Two-level DeepSeek-judged eval harness with per-mode retrieval and cost/latency capture".

Done when: evals/reports/ holds committed JSON for every mode + the app, and every number in
README traces to one of those files. This is the phase that earns the CV bullets - do it carefully.
```

---

## Phase 4 - Regression gate in CI (the Project 1 skill, reapplied)

```
Goal: Make quality non-regressable, exactly like Project 1, but over this bigger engine.

Do this:
1. evals/baselines/retriever_baseline.json: commit the current agentic-mode retriever means.
2. evals/check_regression.py: re-run the retriever eval, compare each metric mean to the baseline,
   exit non-zero if any drops more than a fixed tolerance (0.05) below baseline. Print a clear diff.
3. .github/workflows/eval-gate.yml: on pull_request, checkout, setup-uv, uv sync, then
   `uv run python -m evals.check_regression` with DEEPSEEK_API_KEY from repo secrets.
4. README: add a "Regression gate" subsection describing the merge-blocking behaviour and how to
   reproduce locally.
5. Commit: "Merge-blocking regression gate over the agentic retriever".

Done when: check_regression exits 0 against the committed baseline, and the workflow file is at
repo root (.github/workflows/eval-gate.yml). Note in README that the gate needs the repo secret.
```

---

## Phase 5 - Multi-tenant product layer (the differentiator)

```
Goal: Turn the engine into something that reads as a shipped PRODUCT, not a PoC: per-tenant
isolation, upload, self-serve eval, and visible cost/latency per answer.

Do this:
1. src/api/main.py (FastAPI): auth (simple token or JWT - state which), tenant model, and
   per-tenant ISOLATED doc stores (separate Chroma collection or namespace per tenant; a query
   from tenant A must never retrieve tenant B's docs - add a test that proves this).
2. Upload endpoint: a tenant uploads .md/.txt/.pdf, it is chunked and indexed into THEIR store only.
3. Ask endpoint: returns {answer, sources, latency_ms, est_cost_usd} so cost and latency are
   surfaced per answer (the CV bullet made real).
4. Per-tenant eval endpoint: a tenant runs the Phase 3 harness against their own golden set and
   sees their own scores.
5. A minimal frontend is optional; if time is short, a documented curl/HTTP script is enough.
   Dockerfile for the API. docker-compose if useful.
6. Add tests/test_tenant_isolation.py proving cross-tenant leakage is impossible.
7. Commit: "Multi-tenant product layer: isolated stores, upload, self-serve eval, per-answer cost/latency".

Done when: two tenants can be created, each sees only their own docs (test passes), and an answer
response includes real latency and a cost estimate. State honestly if cost is an estimate vs measured.
```

---

## Phase 6 - Orchestration at scale (phase 2 of the engine, do LAST)

```
Goal: Bounded multi-agent orchestration on top of the engine. Only start this once Phases 1-5
are committed and green.

Do this:
1. src/orchestration/graph.py (LangGraph): a supervisor/router coordinating bounded specialists
   (researcher / fact-checker / writer). HARD cap of 4 supervisor turns so bad routing cannot loop.
2. Per-thread checkpointing (MemorySaver), per-run token accounting, retry with exponential
   backoff (<=3) on transient API failure. Up to 3 concurrent state-isolated agent runs.
3. A script that runs a multi-step query through the graph and prints the token/turn accounting.
4. README: a short architecture note + a diagram (mermaid) of the supervisor/specialist flow.
5. Commit: "Bounded LangGraph orchestration: supervisor + specialists, checkpointing, token accounting".

Done when: a multi-step query completes within the turn cap, token accounting prints real counts,
and the graph refuses to exceed its caps. Capture one real run's accounting into a committed file.
```

---

## After Phase 6 - Packaging and push (do together, at the end)

```
Goal: Make it read senior and get it onto GitHub, private.

Do this:
1. README final pass in JD language: pitch, architecture diagram, real results tables (every
   number citing its report file), "how to run", "how to reproduce evals".
2. Write 3 short ADRs in docs/adr/: (a) hybrid RRF+rerank vs dense-only, with the measured deltas;
   (b) DeepSeek/LiteLLM custom judge vs OpenAI judge; (c) bounded self-correction + turn caps vs
   unbounded agentic loops. Each ADR states the decision, the alternatives, and the evidence.
3. Confirm .env is not tracked. Scan staged content for any key-shaped string before committing.
4. gh repo create Amith-Ganta/agentic-rag-platform --private --source=. --push  (branch: main).
5. Add the DEEPSEEK_API_KEY repo secret so the eval gate can run:
   gh secret set DEEPSEEK_API_KEY --repo Amith-Ganta/agentic-rag-platform

Done when: the private repo exists on main, the eval gate workflow is at repo root, README results
all trace to committed reports, and no secret value is anywhere in git history.
```

---

## Review handoff

When each phase's commit is done, paste the commit hash + the printed "done when" output back
here and I will review it against this spec (honesty of numbers, scope discipline, secret safety)
before you move to the next phase. I do not need to run the code to review it.

## What is deliberately NOT here (deferred, per today's token limit)

- NeMo Guardrails input/output rails and their regression suite.
- PyRIT adversarial red-team / attack-success-rate gate.
- Pure latency/cost/KV-cache gateway benchmarking (that is Project 3).
- Semantic caching can be a stretch goal inside Phase 5 if time allows, otherwise defer.
