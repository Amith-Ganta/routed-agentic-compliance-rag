# AI Job Search Project 2

Multi-tenant agentic RAG platform for routing, hybrid retrieval, bounded self-correction, and per-tenant evaluation. The project is being built in phases so every metric, regression gate, and product claim stays traceable to committed scripts and report files.

Status: in progress

## Results

Numbers will appear here only after a committed eval script prints them and stores the raw output under `evals/reports/`.

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
