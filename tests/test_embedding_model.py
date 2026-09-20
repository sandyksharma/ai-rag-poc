from unittest.mock import Mock

import embeddings.embedding_model as embedding_model


def test_load_model_uses_configured_embedding_model(monkeypatch):
    transformer = Mock(name="transformer")
    sentence_transformer = Mock(return_value=transformer)
    monkeypatch.setattr(embedding_model, "SentenceTransformer", sentence_transformer)

    loaded = embedding_model.load_model()

    sentence_transformer.assert_called_once_with(embedding_model.EMBEDDING_MODEL)
    assert loaded is transformer


def test_generate_delegates_to_model_encode(monkeypatch):
    fake_model = Mock()
    fake_model.encode.return_value = [[0.1, 0.2]]
    monkeypatch.setattr(embedding_model, "load_model", Mock(return_value=fake_model))

    model = embedding_model.EmbeddingModel()

    assert model.generate(["database timeout"]) == [[0.1, 0.2]]
    fake_model.encode.assert_called_once_with(["database timeout"])
