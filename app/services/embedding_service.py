from google import genai
from google.genai import types

from app.core.config import settings


EMBEDDING_DIMENSIONS = 768


class EmbeddingService:
    def __init__(self):
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

    async def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Text cannot be empty")

        response = await self.client.aio.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )

        if not response.embeddings:
            raise RuntimeError("Gemini returned no embeddings")

        values = response.embeddings[0].values

        if values is None or len(values) != EMBEDDING_DIMENSIONS:
            raise RuntimeError("Invalid embedding dimensions")

        return list(values)

    async def close(self):
        await self.client.aio.aclose()

    async def embed_document(self, text: str) -> list[float]:
        return await self.embed(text)


    async def embed_query(self, query: str) -> list[float]:
        return await self.embed(query)