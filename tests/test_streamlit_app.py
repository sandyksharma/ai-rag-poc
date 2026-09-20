import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock


class FakeSpinner:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeStreamlit:
    def __init__(self, query="", clicked=False):
        self.query = query
        self.clicked = clicked
        self.success_messages = []
        self.info_messages = []
        self.writes = []
        self.subheaders = []
        self.dividers = 0

    def cache_resource(self, func=None, **_kwargs):
        if func is None:
            def decorator(inner):
                return inner
            return decorator
        return func

    def spinner(self, *_args, **_kwargs):
        return FakeSpinner()

    def title(self, *_args, **_kwargs):
        return None

    def write(self, *args, **_kwargs):
        self.writes.append(args)

    def success(self, message):
        self.success_messages.append(message)

    def text_input(self, *_args, **_kwargs):
        return self.query

    def button(self, *_args, **_kwargs):
        return self.clicked

    def subheader(self, message):
        self.subheaders.append(message)

    def info(self, message):
        self.info_messages.append(message)

    def divider(self):
        self.dividers += 1


def load_streamlit_app(fake_streamlit, ensure_result=True, search_result=None):
    sys.modules["streamlit"] = fake_streamlit
    ingest_module = SimpleNamespace(ensure_logs_ingested=Mock(return_value=ensure_result))
    search_module = SimpleNamespace(find_similar_logs=Mock(return_value=search_result))
    sys.modules["ingestion.ingest_logs"] = ingest_module
    sys.modules["search.similarity_search"] = search_module
    sys.modules.pop("ui.streamlit_app", None)
    module = importlib.import_module("ui.streamlit_app")
    return module, ingest_module.ensure_logs_ingested, search_module.find_similar_logs


def test_initialize_vector_store_returns_ingestion_result():
    fake_streamlit = FakeStreamlit()
    module, ensure_logs_ingested, _find_similar_logs = load_streamlit_app(fake_streamlit, ensure_result=True)

    assert module.initialize_vector_store() is True
    assert ensure_logs_ingested.call_count == 2


def test_app_displays_matching_results():
    fake_streamlit = FakeStreamlit(query="payment timeout", clicked=True)
    search_result = {
        "documents": [["payment timeout", "unrelated issue"]],
        "metadatas": [[
            {"service": "payments", "severity": "high"},
            {"service": "orders", "severity": "low"},
        ]],
        "distances": [[1.2, 2.1]],
    }

    _module, _ensure_logs_ingested, find_similar_logs = load_streamlit_app(
        fake_streamlit,
        ensure_result=True,
        search_result=search_result,
    )

    find_similar_logs.assert_called_once_with("payment timeout")
    assert "Logs were ingested into the vector database." in fake_streamlit.success_messages
    assert "Similar Failures Found" in fake_streamlit.subheaders
    assert ("Failure:", "payment timeout") in fake_streamlit.writes
    assert fake_streamlit.dividers == 1
    assert not fake_streamlit.info_messages


def test_app_shows_info_when_no_results_meet_threshold():
    fake_streamlit = FakeStreamlit(query="payment timeout", clicked=True)
    search_result = {
        "documents": [["payment timeout"]],
        "metadatas": [[{"service": "payments", "severity": "high"}]],
        "distances": [[2.2]],
    }

    _module, _ensure_logs_ingested, _find_similar_logs = load_streamlit_app(
        fake_streamlit,
        ensure_result=False,
        search_result=search_result,
    )

    assert fake_streamlit.success_messages == []
    assert fake_streamlit.info_messages == [
        "No close matches found for this query. Try a more specific error message."
    ]
