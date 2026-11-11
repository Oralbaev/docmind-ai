import asyncio
from types import SimpleNamespace

import pytest

from app.services.embedding_service import EMBEDDING_DIMENSIONS, EmbeddingService
from app.routers.documents import _validate_signature


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, list):
            return self.response.pop(0)
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


def test_large_batch_is_split_without_reordering():
    vectors = [[float(i)] * EMBEDDING_DIMENSIONS for i in range(101)]
    responses = [
        SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in vectors[:100]]),
        SimpleNamespace(embeddings=[SimpleNamespace(values=vectors[100])]),
    ]
    service, models = make_service(responses)

    result = asyncio.run(service.embed_documents([f"chunk-{i}" for i in range(101)]))

    assert result == vectors
    assert [len(call["contents"]) for call in models.calls] == [100, 1]


def test_upload_signature_checks_extension_against_content():
    assert _validate_signature("notes.txt", "Привет".encode())
    assert _validate_signature("scan.pdf", b"%PDF-1.7")
    assert not _validate_signature("scan.pdf", b"not a pdf")
    assert not _validate_signature("notes.txt", b"\xff")
