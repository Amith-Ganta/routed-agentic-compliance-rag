# Retrieval Augmented Generation

Retrieval augmented generation combines a search step with a generation step. A user question is first turned into a retrieval query, then the system fetches relevant text chunks from a knowledge base, and finally a language model writes an answer using only the retrieved context.

This approach helps when a model needs fresh, private, or domain specific information that should not be memorized in the model weights. It also makes it easier to show sources and debug why an answer was produced.

