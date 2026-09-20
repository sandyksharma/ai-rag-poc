# Utility that reads the raw JSON dataset used by the project.
# This keeps all log loading logic centralized so ingestion, retrieval, and testing all work against
# the same data structure.

import json


def load_logs(file_path):
    with open(file_path, "r") as f:
        logs = json.load(f)

    return logs