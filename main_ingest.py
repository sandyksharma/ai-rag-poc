# CLI entry point for rebuilding the local vector log knowledge base.
# This script is useful when you want to re-index the sample logs after changing the dataset,
# the embedding model, or the retrieval strategy.

import argparse

from ingestion.ingest_logs import ingest_logs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing embeddings before ingesting logs again.",
    )
    args = parser.parse_args()

    print("Starting log ingestion process...")
    ingest_logs(reset_db=args.reset)
