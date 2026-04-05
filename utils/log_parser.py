import json


def load_logs(file_path):

    with open(file_path, "r") as f:
        logs = json.load(f)

    return logs