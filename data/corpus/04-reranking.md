# Reranking

Reranking takes a set of candidate passages from a first-stage retriever and reorders them with a stronger model. The first stage emphasizes speed, while reranking improves precision.

This is useful when many retrieved chunks look relevant at the embedding level but only a few actually answer the user question directly.

