import chromadb
from chromadb.config import Settings
from config.settings import VECTOR_COLLECTION


class ChromaVectorDB:

    def __init__(self):

        self.client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )

        self.collection = self.client.get_or_create_collection(
            name=VECTOR_COLLECTION
        )

    def insert(self, ids, documents, embeddings, metadata):

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadata
        )

    def count(self):

        return self.collection.count()

    def reset(self):

        reset_completed = self.client.reset()
        self.collection = self.client.get_or_create_collection(
            name=VECTOR_COLLECTION
        )
        return reset_completed

    def search(self, embedding, top_k):

        results = self.collection.query(
            query_embeddings=embedding,
            n_results=top_k
        )

        return results
