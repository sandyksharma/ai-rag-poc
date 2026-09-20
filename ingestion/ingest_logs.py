# Ingestion pipeline for the vectorized log database.
# This module is responsible for reading raw log content, converting it to embeddings,
# and storing the resulting vectors in ChromaDB so later queries can find similar incidents.

import os
import sys
from utils.log_parser import load_logs
from embeddings.embedding_model import EmbeddingModel
from vectordb.chroma_client import ChromaVectorDB

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def ingest_logs(reset_db=False):
    """Read the JSON log dataset and import it into the vector database."""

    # Load the raw log records from the project dataset.
    logs = load_logs("data/logs.json")

    # Extract the message content so each log entry becomes a searchable document.
    messages = [log["message"] for log in logs]
    print("Log messages extracted from input data")
    print(messages)

    # Create the embedding model and convert all log messages to vectors.
    embedding_model = EmbeddingModel()
    embeddings = embedding_model.generate(messages)
    print("Embeddings generated for log messages")
    print(embeddings)

    # Use each log's ID as the vector record identifier for consistent retrieval.
    ids = [log["log_id"] for log in logs]
    print("Unique IDs created for log entries")
    print(ids)

    # Store metadata that helps explain what service and severity each matching log belongs to.
    metadata = [
        {
            "service": log["service"],
            "severity": log["severity"]
        }
        for log in logs
    ]
    print("Metadata prepared for log entries")
    print(metadata)

    # Initialize the ChromaDB wrapper and insert the records.
    vectordb = ChromaVectorDB()

    if reset_db:
        print("Resetting Vector DB before inserting logs.")
        vectordb.reset()

    vectordb.insert(
        ids=ids,
        documents=messages,
        embeddings=embeddings,
        metadata=metadata
    )

    print("Logs successfully stored in Vector DB")


def ensure_logs_ingested():
    """Ensure the local database contains log data; reset if it already exists."""

    vectordb = ChromaVectorDB()

    # If data already exists, start from a clean collection before re-importing.
    if vectordb.count() > 0:
        print("Vector DB already contains ingested logs. Resetting Collection.")
        vectordb.reset()

    print("Vector DB is empty. Starting ingestion.")
    ingest_logs()
    return True
