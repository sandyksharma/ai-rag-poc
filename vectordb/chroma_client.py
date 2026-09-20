# Thin wrapper around ChromaDB for storing and querying vectorized log data.
# This class isolates the rest of the project from Chroma-specific details so searches,
# ingestion, and agent orchestration can remain clean and testable.

import chromadb
from chromadb.config import Settings
from config.settings import VECTOR_COLLECTION


class ChromaVectorDB:
    """Persistence wrapper for the log-embedding collection."""

    MAX_BATCH_SIZE = 5000

    def __init__(self):
        # Persistent local database directory keeps the vector store between runs.
        self.client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

        self.collection = self.client.get_or_create_collection(
            name=VECTOR_COLLECTION
        )

    def insert(self, ids, documents, embeddings, metadata):
        # Chroma handles large insert batches better when done in chunks.
        batch_size = self.MAX_BATCH_SIZE
        total = len(ids)

        for start in range(0, total, batch_size):
            end = start + batch_size
            self.collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadata[start:end]
            )

    def count(self):
        # Return the total number of stored log vectors.
        return self.collection.count()

    def reset(self):
        # Clear the entire collection so the project can be re-ingested cleanly.
        reset_completed = self.client.reset()
        self.collection = self.client.get_or_create_collection(
            name=VECTOR_COLLECTION
        )
        return reset_completed

    def search(self, embedding, top_k):
        # Query the vector store for the nearest documents based on the current embedding.
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=top_k
        )

        return results
