# Prompt Injection

Prompt injection is an attack where retrieved or user supplied text tries to override the system instructions. RAG systems are especially exposed because they read external text directly into the prompt.

Defenses include instruction hierarchy, source filtering, grounding checks, and refusing to follow instructions that come from untrusted context.

