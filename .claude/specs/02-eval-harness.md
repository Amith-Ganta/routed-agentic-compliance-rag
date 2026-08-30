# 02 Eval Harness

## Purpose
Build a two-level evaluation harness that scores retrieval separately from the full application.

## In scope
- Retriever-only evaluation.
- Full application evaluation.
- DeepSeek judge via LiteLLM with JSON-mode output.
- Contextual recall, precision, relevancy, faithfulness, answer relevancy, and G-Eval correctness.
- Per-run retrieval latency and judge cost capture.

## Out of scope
- Product APIs.
- Orchestration scale-out.
- External benchmark datasets.

## Done when
- Each mode produces a committed report file.
- Retriever and application metrics are measured separately.
- Every metric in the README traces back to a report file.

## Deferred
- Advanced red-teaming.
- Non-DeepSeek judge variants.
- Dashboards and charting.

