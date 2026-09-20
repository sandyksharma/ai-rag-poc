# Central configuration values for the log intelligence stack.
# Keeping these in one file makes it easy to tune retrieval behavior,
# model selection, and collection naming without changing many modules.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chroma collection name used to store the log embeddings.
VECTOR_COLLECTION = "application_logs"

# Default number of nearest log matches to retrieve for a given query.
TOP_K_RESULTS = 10