# 04 Tenancy Product

## Purpose
Turn the engine into a product with tenant isolation, uploads, and visible answer-level cost and latency.

## In scope
- Authentication.
- Tenant-isolated document stores.
- Upload and ask endpoints.
- Per-tenant evaluation runs.
- Cost and latency surfaced per answer.

## Out of scope
- Deep orchestration scale-out.
- Final regression policy.
- Optional frontend polish.

## Done when
- Tenant A cannot retrieve Tenant B documents.
- Uploads stay inside the correct tenant store.
- Answers return latency and an estimated cost.

## Deferred
- Semantic caching.
- Advanced billing integration.
- Full UI beyond simple API usage.

