from unittest.mock import Mock

import vectordb.chroma_client as chroma_client


def test_init_creates_persistent_client_and_collection(monkeypatch):
    settings = Mock(name="settings")
    settings_ctor = Mock(return_value=settings)
    collection = Mock(name="collection")
    client = Mock(name="client")
    client.get_or_create_collection.return_value = collection
    persistent_client = Mock(return_value=client)

    monkeypatch.setattr(chroma_client, "Settings", settings_ctor)
    monkeypatch.setattr(chroma_client.chromadb, "PersistentClient", persistent_client)

    db = chroma_client.ChromaVectorDB()

    settings_ctor.assert_called_once_with(anonymized_telemetry=False, allow_reset=True)
    persistent_client.assert_called_once_with(path="./chroma_db", settings=settings)
    client.get_or_create_collection.assert_called_once_with(name=chroma_client.VECTOR_COLLECTION)
    assert db.collection is collection


def test_insert_sends_data_in_batches(monkeypatch):
    db = chroma_client.ChromaVectorDB.__new__(chroma_client.ChromaVectorDB)
    db.MAX_BATCH_SIZE = 2
    db.collection = Mock()

    db.insert(
        ids=["1", "2", "3"],
        documents=["a", "b", "c"],
        embeddings=[[1], [2], [3]],
        metadata=[{"m": 1}, {"m": 2}, {"m": 3}],
    )

    assert db.collection.add.call_count == 2
    first_call = db.collection.add.call_args_list[0].kwargs
    second_call = db.collection.add.call_args_list[1].kwargs
    assert first_call["ids"] == ["1", "2"]
    assert second_call["ids"] == ["3"]


def test_count_returns_collection_count():
    db = chroma_client.ChromaVectorDB.__new__(chroma_client.ChromaVectorDB)
    db.collection = Mock()
    db.collection.count.return_value = 7

    assert db.count() == 7


def test_reset_resets_client_and_recreates_collection():
    db = chroma_client.ChromaVectorDB.__new__(chroma_client.ChromaVectorDB)
    db.client = Mock()
    new_collection = Mock()
    db.client.get_or_create_collection.return_value = new_collection
    db.client.reset.return_value = True

    assert db.reset() is True
    db.client.reset.assert_called_once_with()
    db.client.get_or_create_collection.assert_called_once_with(name=chroma_client.VECTOR_COLLECTION)
    assert db.collection is new_collection


def test_search_queries_collection():
    db = chroma_client.ChromaVectorDB.__new__(chroma_client.ChromaVectorDB)
    db.collection = Mock()
    db.collection.query.return_value = {"documents": [["match"]]}

    results = db.search([[0.1, 0.2]], 3)

    assert results == {"documents": [["match"]]}
    db.collection.query.assert_called_once_with(query_embeddings=[[0.1, 0.2]], n_results=3)
