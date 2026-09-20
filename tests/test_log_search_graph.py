from unittest.mock import Mock

import orchestration.log_search_graph as log_search_graph
import search.similarity_search as similarity_search


def setup_function():
    log_search_graph.build_log_search_graph.cache_clear()


def test_log_search_graph_normalizes_embeds_and_searches(monkeypatch):
    embedding_model = Mock()
    embedding_model.generate.return_value = [[0.3, 0.4]]
    vectordb = Mock()
    vectordb.search.return_value = {"documents": [["payment timeout"]]}

    monkeypatch.setattr(similarity_search, "normalize_query", Mock(return_value="payment timeout"))
    monkeypatch.setattr(log_search_graph, "EmbeddingModel", Mock(return_value=embedding_model))
    monkeypatch.setattr(log_search_graph, "ChromaVectorDB", Mock(return_value=vectordb))

    results = log_search_graph.run_log_search_graph("paymnt time out", top_k=3)

    assert results == {"documents": [["payment timeout"]]}
    similarity_search.normalize_query.assert_called_once_with("paymnt time out")
    embedding_model.generate.assert_called_once_with(["payment timeout"])
    vectordb.search.assert_called_once_with([[0.3, 0.4]], 3)
