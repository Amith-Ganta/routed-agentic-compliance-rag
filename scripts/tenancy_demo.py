from __future__ import annotations

import json
from pathlib import Path

from src.rag.ingest import build_tenant_index
from src.rag.retriever_hybrid import retrieve_hybrid
from src.rag.tenant_context import tenant_corpus_dir, use_tenant


def _write_doc(tenant_id: str, filename: str, content: str) -> None:
    corpus_dir = tenant_corpus_dir(tenant_id)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / filename).write_text(content, encoding="utf-8")


def main() -> None:
    _write_doc("tenant-a", "tenant-a.md", "ALPHA_SENTINEL_PHRASE unique to tenant a")
    _write_doc("tenant-b", "tenant-b.md", "BETA_SENTINEL_PHRASE unique to tenant b")
    build_tenant_index("tenant-a")
    build_tenant_index("tenant-b")

    with use_tenant("tenant-a"):
        a_docs = retrieve_hybrid("ALPHA_SENTINEL_PHRASE", top_k=5)
        a_can_see_a = any("ALPHA_SENTINEL_PHRASE" in doc.page_content for doc in a_docs)

    with use_tenant("tenant-b"):
        b_docs = retrieve_hybrid("ALPHA_SENTINEL_PHRASE", top_k=5)
        b_can_see_a = any("ALPHA_SENTINEL_PHRASE" in doc.page_content for doc in b_docs)

    isolation_holds = a_can_see_a and not b_can_see_a
    report = {
        "run": "phase4-tenancy",
        "tenants": ["tenant-a", "tenant-b"],
        "isolation_holds": isolation_holds,
        "a_can_see_a": a_can_see_a,
        "b_can_see_a": b_can_see_a,
        "notes": "retrieval-layer isolation proven without live LLM calls",
    }
    report_path = Path("evals/reports/tenancy_isolation.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"tenancy isolation: holds={isolation_holds} a_sees_a={a_can_see_a} b_sees_a={b_can_see_a}")


if __name__ == "__main__":
    main()
