# 03 Orchestration

## Purpose
Add bounded LangGraph orchestration on top of the agentic RAG engine.

## In scope
- Supervisor and specialist graph design.
- Per-thread checkpointing.
- Retry with backoff.
- Hard turn caps and token accounting.

## Out of scope
- Tenant product APIs.
- Initial corpus and baseline retrieval work.
- External workflow tools.

## Done when
- The graph completes within a fixed turn cap.
- Token usage is captured per run.
- Retries stay bounded and do not loop forever.

## Deferred
- Multi-run concurrency tuning.
- Advanced memory policies.
- Cross-tenant orchestration.

