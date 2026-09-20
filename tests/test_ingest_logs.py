from unittest.mock import Mock

import ingestion.ingest_logs as ingest_module


def test_ingest_logs_builds_payload_and_inserts(monkeypatch):
    logs = [
        {
            "log_id": "1",
            "message": "payment timeout",
            "service": "payments",
            "severity": "high",
        },
        {
            "log_id": "2",
            "message": "db connection lost",
            "service": "database",
            "severity": "critical",
        },
    ]
    embedding_model = Mock()
    embedding_model.generate.return_value = [[0.1], [0.2]]
    vectordb = Mock()

    monkeypatch.setattr(ingest_module, "load_logs", Mock(return_value=logs))
    monkeypatch.setattr(ingest_module, "EmbeddingModel", Mock(return_value=embedding_model))
    monkeypatch.setattr(ingest_module, "ChromaVectorDB", Mock(return_value=vectordb))

    ingest_module.ingest_logs()

    embedding_model.generate.assert_called_once_with(["payment timeout", "db connection lost"])
    vectordb.insert.assert_called_once_with(
        ids=["1", "2"],
        documents=["payment timeout", "db connection lost"],
        embeddings=[[0.1], [0.2]],
        metadata=[
            {"service": "payments", "severity": "high"},
            {"service": "database", "severity": "critical"},
        ],
    )


def test_ingest_logs_resets_before_insert_when_requested(monkeypatch):
    logs = [
        {
            "log_id": "1",
            "message": "payment timeout",
            "service": "payments",
            "severity": "high",
        }
    ]
    embedding_model = Mock()
    embedding_model.generate.return_value = [[0.1]]
    vectordb = Mock()

    monkeypatch.setattr(ingest_module, "load_logs", Mock(return_value=logs))
    monkeypatch.setattr(ingest_module, "EmbeddingModel", Mock(return_value=embedding_model))
    monkeypatch.setattr(ingest_module, "ChromaVectorDB", Mock(return_value=vectordb))

    ingest_module.ingest_logs(reset_db=True)

    vectordb.reset.assert_called_once_with()
    vectordb.insert.assert_called_once()


def test_ensure_logs_ingested_resets_non_empty_db(monkeypatch):
    vectordb = Mock()
    vectordb.count.return_value = 5
    monkeypatch.setattr(ingest_module, "ChromaVectorDB", Mock(return_value=vectordb))
    ingest_logs = Mock()
    monkeypatch.setattr(ingest_module, "ingest_logs", ingest_logs)

    result = ingest_module.ensure_logs_ingested()

    assert result is True
    vectordb.reset.assert_called_once_with()
    ingest_logs.assert_called_once_with()


def test_ensure_logs_ingested_skips_reset_for_empty_db(monkeypatch):
    vectordb = Mock()
    vectordb.count.return_value = 0
    monkeypatch.setattr(ingest_module, "ChromaVectorDB", Mock(return_value=vectordb))
    ingest_logs = Mock()
    monkeypatch.setattr(ingest_module, "ingest_logs", ingest_logs)

    result = ingest_module.ensure_logs_ingested()

    assert result is True
    vectordb.reset.assert_not_called()
    ingest_logs.assert_called_once_with()
