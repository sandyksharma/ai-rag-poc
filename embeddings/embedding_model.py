from sentence_transformers import SentenceTransformer
import streamlit as st
from config.settings import EMBEDDING_MODEL
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@st.cache_resource
def load_model():
    return SentenceTransformer(EMBEDDING_MODEL)


class EmbeddingModel:

    def __init__(self):
        self.model = load_model()

    def generate(self, texts):
        print("Generating embeddings for input texts...")
        return self.model.encode(texts)