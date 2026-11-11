import asyncio
from types import SimpleNamespace

import pytest

from app.services.embedding_service import EMBEDDING_DIMENSIONS, EmbeddingService


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def make_service(response):
    service = EmbeddingService.__new__(EmbeddingService)
    models = FakeModels(response)
    service.client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return service, models


def test_batch_embedding_returns_vectors_in_order():
    vectors = [[float(i)] * EMBEDDING_DIMENSIONS for i in (1, 2)]
    service, models = make_service(
        SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in vectors])
    )

    result = asyncio.run(service.embed_documents(["first", "second"]))

    assert result == vectors
    assert models.calls[0]["contents"] == ["first", "second"]


def test_batch_embedding_rejects_invalid_response_size():
    service, _ = make_service(SimpleNamespace(embeddings=[]))

    with pytest.raises(RuntimeError, match="number of embeddings"):
        asyncio.run(service.embed_documents(["text"]))


def test_batch_embedding_empty_input_skips_provider():
    service, models = make_service(SimpleNamespace(embeddings=[]))

    assert asyncio.run(service.embed_documents([])) == []
    assert models.calls == []
