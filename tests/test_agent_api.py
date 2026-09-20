from fastapi.testclient import TestClient

from api.app import app
from orchestration.agent_graph import run_log_agent


def test_run_log_agent_returns_conversational_answer(monkeypatch):
    def fake_search_logs_tool(query):
        return {
            "documents": [["Connection timeout while calling payment API"]],
            "metadatas": [[{"service": "payment-api", "severity": "critical"}]],
            "distances": [[0.12]],
        }

    monkeypatch.setattr("orchestration.agent_graph.search_logs_tool", fake_search_logs_tool)

    result = run_log_agent("database connection timeout")

    assert result["query"] == "database connection timeout"
    assert "payment API" in result["answer"]
    assert result["tool_calls"][0]["tool"] == "search_logs"


def test_run_log_agent_skips_rag_for_generic_question(monkeypatch):
    def fail_search_logs_tool(query, top_k=None):
        raise AssertionError("RAG should be skipped for generic questions")

    def fake_llm(messages):
        return "In general, a timeout happens when a service waits too long for a dependency response."

    monkeypatch.setattr("orchestration.agent_graph.search_logs_tool", fail_search_logs_tool)
    monkeypatch.setattr("orchestration.agent_graph.call_local_llm", fake_llm)

    result = run_log_agent("what is a database timeout")

    assert result["decision"] == "respond"
    assert result["tool_calls"] == []
    assert "timeout happens" in result["answer"]
    assert "skipped RAG" in result["reasoning"]


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agent_chat_endpoint(monkeypatch):
    def fake_search_logs_tool(query):
        return {
            "documents": [["Database connection timeout in customer service"]],
            "metadatas": [[{"service": "customer-service", "severity": "high"}]],
            "distances": [[0.21]],
        }

    monkeypatch.setattr("orchestration.agent_graph.search_logs_tool", fake_search_logs_tool)
    client = TestClient(app)

    response = client.post("/api/agent/chat", json={"query": "database connection timeout"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "database connection timeout"
    assert "customer service" in payload["answer"].lower()


def test_feedback_endpoint_records_dislike_and_returns_refined_answer(monkeypatch):
    def fake_search_logs_tool(query):
        return {
            "documents": [["Database connection timeout in inventory service"]],
            "metadatas": [[{"service": "inventory-service", "severity": "critical"}]],
            "distances": [[0.18]],
        }

    monkeypatch.setattr("orchestration.agent_graph.search_logs_tool", fake_search_logs_tool)
    client = TestClient(app)

    response = client.post(
        "/api/agent/feedback",
        json={
            "query": "db connection timeout",
            "reaction": "dislike",
            "message": "This answer was too generic.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reaction"] == "dislike"
    assert payload["status"] == "recorded"
    assert "refined_answer" in payload
    assert "inventory" in payload["refined_answer"].lower()
