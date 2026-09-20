# Query normalization and similarity-helper layer.
# This file improves user-supplied search text before the vector retrieval step so typo-robust or
# split-word queries still match meaningful historical log messages.

from difflib import get_close_matches
from functools import lru_cache
import re

from config.settings import TOP_K_RESULTS
from utils.log_parser import load_logs


@lru_cache(maxsize=1)
def get_log_vocabulary():
    # Build a vocabulary from existing log messages so we can spot likely misspellings and merged tokens.
    logs = load_logs("data/logs.json")
    vocabulary = set()

    for log in logs:
        words = re.findall(r"\b\w+\b", log["message"].lower())
        vocabulary.update(words)

    return vocabulary


def merge_split_tokens(tokens, vocabulary):
    # Some user inputs may group words incorrectly (for example, 'connectiontimeout').
    # If the concatenated token is present in the log vocabulary, treat it as a single phrase.
    merged_tokens = []
    index = 0

    while index < len(tokens):
        if index + 1 < len(tokens):
            combined_token = tokens[index] + tokens[index + 1]
            if combined_token in vocabulary:
                merged_tokens.append(combined_token)
                index += 2
                continue

        merged_tokens.append(tokens[index])
        index += 1

    return merged_tokens


def correct_typos(tokens, vocabulary):
    # Replace near-miss tokens with the closest known word from the log corpus.
    corrected_tokens = []

    for token in tokens:
        if token in vocabulary or len(token) < 4:
            corrected_tokens.append(token)
            continue

        closest_match = get_close_matches(token, vocabulary, n=1, cutoff=0.8)
        corrected_tokens.append(closest_match[0] if closest_match else token)

    return corrected_tokens


def normalize_query(query):
    # Convert a free-form query into the set of log-like tokens most likely to match the stored dataset.
    vocabulary = get_log_vocabulary()
    tokens = re.findall(r"\b\w+\b", query.lower().strip())
    tokens = merge_split_tokens(tokens, vocabulary)
    tokens = correct_typos(tokens, vocabulary)
    return " ".join(tokens)


def find_similar_logs(query):
    # This helper is the user-facing search wrapper. It delegates to the retrieval graph.
    from orchestration.log_search_graph import run_log_search_graph

    return run_log_search_graph(query, TOP_K_RESULTS)
