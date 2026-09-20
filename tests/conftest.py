import sys
import types
import importlib.util
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Spinner:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _cache_resource(func=None, **_kwargs):
    if func is None:
        def decorator(inner):
            return inner
        return decorator
    return func


streamlit = types.ModuleType("streamlit")
streamlit.cache_resource = _cache_resource
streamlit.spinner = lambda *_args, **_kwargs: _Spinner()
streamlit.title = lambda *_args, **_kwargs: None
streamlit.write = lambda *_args, **_kwargs: None
streamlit.success = lambda *_args, **_kwargs: None
streamlit.text_input = lambda *_args, **_kwargs: ""
streamlit.button = lambda *_args, **_kwargs: False
streamlit.subheader = lambda *_args, **_kwargs: None
streamlit.info = lambda *_args, **_kwargs: None
streamlit.divider = lambda *_args, **_kwargs: None
sys.modules.setdefault("streamlit", streamlit)


sentence_transformers = types.ModuleType("sentence_transformers")


class _SentenceTransformer:
    def __init__(self, model_name):
        self.model_name = model_name

    def encode(self, texts):
        return [[float(index)] for index, _text in enumerate(texts)]


sentence_transformers.SentenceTransformer = _SentenceTransformer
sys.modules.setdefault("sentence_transformers", sentence_transformers)


chromadb = types.ModuleType("chromadb")


class _Collection:
    def __init__(self):
        self.add_calls = []
        self.query_calls = []
        self.count_value = 0

    def add(self, **kwargs):
        self.add_calls.append(kwargs)

    def count(self):
        return self.count_value

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


class _PersistentClient:
    def __init__(self, path, settings):
        self.path = path
        self.settings = settings
        self.collection = _Collection()
        self.reset_called = False

    def get_or_create_collection(self, name):
        self.collection_name = name
        return self.collection

    def reset(self):
        self.reset_called = True
        return True


chromadb.PersistentClient = _PersistentClient
sys.modules.setdefault("chromadb", chromadb)

chromadb_config = types.ModuleType("chromadb.config")


class _Settings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


chromadb_config.Settings = _Settings
sys.modules.setdefault("chromadb.config", chromadb_config)


if importlib.util.find_spec("langgraph") is None:
    langgraph = types.ModuleType("langgraph")
    langgraph_graph = types.ModuleType("langgraph.graph")
    langgraph_graph.START = "__start__"
    langgraph_graph.END = "__end__"

    class _CompiledStateGraph:
        def __init__(self, graph):
            self.graph = graph

        def invoke(self, state):
            current = self.graph.entry_point
            while current != langgraph_graph.END:
                update = self.graph.nodes[current](state)
                state = {**state, **update}
                current = self.graph.edges[current]
            return state

    class _StateGraph:
        def __init__(self, _state_schema):
            self.nodes = {}
            self.edges = {}
            self.entry_point = None

        def add_node(self, name, node):
            self.nodes[name] = node

        def add_edge(self, start, end):
            if start == langgraph_graph.START:
                self.entry_point = end
            else:
                self.edges[start] = end

        def compile(self):
            return _CompiledStateGraph(self)

    langgraph_graph.StateGraph = _StateGraph
    langgraph.graph = langgraph_graph
    sys.modules.setdefault("langgraph", langgraph)
    sys.modules.setdefault("langgraph.graph", langgraph_graph)
