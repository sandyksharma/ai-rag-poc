from functools import lru_cache
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from config.settings import TOP_K_RESULTS
from embeddings.embedding_model import EmbeddingModel
from vectordb.chroma_client import ChromaVectorDB


class LogSearchState(TypedDict, total=False):
    query: str
    normalized_query: str
    query_embedding: List[List[float]]
    top_k: int
    results: Dict[str, Any]


def normalize_query_node(state: LogSearchState) -> LogSearchState:
    from search.similarity_search import normalize_query

    return {"normalized_query": normalize_query(state["query"])}


def generate_embedding_node(state: LogSearchState) -> LogSearchState:
    embedding_model = EmbeddingModel()
    embedding = embedding_model.generate([state["normalized_query"]])
    return {"query_embedding": embedding}


def search_vector_db_node(state: LogSearchState) -> LogSearchState:
    vectordb = ChromaVectorDB()
    results = vectordb.search(state["query_embedding"], state.get("top_k", TOP_K_RESULTS))
    return {"results": results}


@lru_cache(maxsize=1)
def build_log_search_graph():
    graph = StateGraph(LogSearchState)
    graph.add_node("normalize_query", normalize_query_node)
    graph.add_node("generate_embedding", generate_embedding_node)
    graph.add_node("search_vector_db", search_vector_db_node)

    graph.add_edge(START, "normalize_query")
    graph.add_edge("normalize_query", "generate_embedding")
    graph.add_edge("generate_embedding", "search_vector_db")
    graph.add_edge("search_vector_db", END)

    return graph.compile()


def run_log_search_graph(query: str, top_k: int = TOP_K_RESULTS) -> Dict[str, Any]:
    graph = build_log_search_graph()
    state = graph.invoke({"query": query, "top_k": top_k})
    return state["results"]
