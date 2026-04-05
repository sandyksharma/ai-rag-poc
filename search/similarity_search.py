from difflib import get_close_matches
from functools import lru_cache
import re

from embeddings.embedding_model import EmbeddingModel
from vectordb.chroma_client import ChromaVectorDB
from config.settings import TOP_K_RESULTS
from utils.log_parser import load_logs


@lru_cache(maxsize=1)
def get_log_vocabulary():

    logs = load_logs("data/logs.json")
    vocabulary = set()

    for log in logs:
        words = re.findall(r"\b\w+\b", log["message"].lower())
        vocabulary.update(words)

    return vocabulary


def merge_split_tokens(tokens, vocabulary):

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

    corrected_tokens = []

    for token in tokens:
        if token in vocabulary or len(token) < 4:
            corrected_tokens.append(token)
            continue

        closest_match = get_close_matches(token, vocabulary, n=1, cutoff=0.8)
        corrected_tokens.append(closest_match[0] if closest_match else token)

    return corrected_tokens


def normalize_query(query):

    vocabulary = get_log_vocabulary()
    tokens = re.findall(r"\b\w+\b", query.lower().strip())
    tokens = merge_split_tokens(tokens, vocabulary)
    tokens = correct_typos(tokens, vocabulary)
    return " ".join(tokens)


def find_similar_logs(query):

    embedding_model = EmbeddingModel()

    vectordb = ChromaVectorDB()

    normalized_query = normalize_query(query)
    query_embedding = embedding_model.generate([normalized_query])

    results = vectordb.search(query_embedding, TOP_K_RESULTS)

    return results
