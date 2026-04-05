import os
import sys
from utils.log_parser import load_logs
from embeddings.embedding_model import EmbeddingModel
from vectordb.chroma_client import ChromaVectorDB

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def ingest_logs():

    logs = load_logs("data/logs.json")

    messages = [log["message"] for log in logs]
    print("Log messages extracted from input data")
    print(messages)

    embedding_model = EmbeddingModel()

    # Generate embeddings for log messages
    embeddings = embedding_model.generate(messages)
    print("Embeddings generated for log messages")
    print(embeddings)

    # Create unique IDs for each log entry
    ids = [log["log_id"] for log in logs]
    print("Unique IDs created for log entries")
    print(ids)

    # Prepare metadata for each log entry
    metadata = [
        {
            "service": log["service"],
            "severity": log["severity"]
        }
        for log in logs
    ]
    print("Metadata prepared for log entries")
    print(metadata)

    # Initialize Vector DB client and insert log data
    vectordb = ChromaVectorDB()

    # Insert log data into Vector DB
    vectordb.insert(
        ids=ids,
        documents=messages,
        embeddings=embeddings,
        metadata=metadata
    )

    print("Logs successfully stored in Vector DB")


def ensure_logs_ingested():

    vectordb = ChromaVectorDB()
    
    # Clear existing data in the collection for fresh ingestion
    if vectordb.count() > 0:
        print("Vector DB already contains ingested logs. Resetting Collection.")
        vectordb.reset()

    print("Vector DB is empty. Starting ingestion.")
    ingest_logs()
    return True
