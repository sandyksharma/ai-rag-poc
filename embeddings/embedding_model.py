# This module wraps the embedding model used to transform log text into vector representations.
# The vectors are later compared in ChromaDB to find historic logs that are semantically closest
# to the user’s current incident description.

from sentence_transformers import SentenceTransformer
import streamlit as st
from config.settings import EMBEDDING_MODEL
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Cache the embedding model so it is created only once per session.
@st.cache_resource
def load_model():
    return SentenceTransformer(EMBEDDING_MODEL)


class EmbeddingModel:
    """Thin wrapper around the sentence-transformers model for log indexing and search."""

    def __init__(self):
        self.model = load_model()

    def generate(self, texts):
        # Encode one or many log messages into a vector representation that ChromaDB can store and query.
        print("Generating embeddings for input texts...")
        return self.model.encode(texts)