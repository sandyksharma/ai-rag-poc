from unittest.mock import Mock

import search.similarity_search as similarity_search


def setup_function():
    similarity_search.get_log_vocabulary.cache_clear()


def test_get_log_vocabulary_extracts_unique_words(monkeypatch):
    logs = [
        {"message": "Payment API timeout"},
        {"message": "Timeout during customer load"},
    ]
    monkeypatch.setattr(similarity_search, "load_logs", Mock(return_value=logs))

    vocabulary = similarity_search.get_log_vocabulary()

    assert {"payment", "api", "timeout", "during", "customer", "load"} <= vocabulary


def test_get_log_vocabulary_uses_cache(monkeypatch):
    loader = Mock(return_value=[{"message": "one two"}])
    monkeypatch.setattr(similarity_search, "load_logs", loader)

    first = similarity_search.get_log_vocabulary()
    second = similarity_search.get_log_vocabulary()

    assert first == second
    loader.assert_called_once_with("data/logs.json")


def test_merge_split_tokens_combines_adjacent_known_word():
    merged = similarity_search.merge_split_tokens(["time", "out", "error"], {"timeout", "error"})

    assert merged == ["timeout", "error"]


def test_correct_typos_replaces_close_matches_and_keeps_short_tokens():
    corrected = similarity_search.correct_typos(["timout", "db", "error"], {"timeout", "db", "error"})

    assert corrected == ["timeout", "db", "error"]


def test_normalize_query_merges_and_corrects(monkeypatch):
    monkeypatch.setattr(
        similarity_search,
        "get_log_vocabulary",
        Mock(return_value={"timeout", "database", "error"}),
    )

    normalized = similarity_search.normalize_query(" Time out databaze error ")

    assert normalized == "timeout database error"


def test_find_similar_logs_normalizes_query_and_searches(monkeypatch):
    run_log_search_graph = Mock(return_value={"documents": [["payment timeout"]]})
    import orchestration.log_search_graph as log_search_graph
    monkeypatch.setattr(log_search_graph, "run_log_search_graph", run_log_search_graph)

    results = similarity_search.find_similar_logs("paymnt time out")

    assert results == {"documents": [["payment timeout"]]}
    run_log_search_graph.assert_called_once_with("paymnt time out", similarity_search.TOP_K_RESULTS)
