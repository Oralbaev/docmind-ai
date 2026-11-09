from dataclasses import dataclass

from app.services.document_parser import ParsedPage


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    page_number: int | None


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if not 0 <= overlap < chunk_size:
        raise ValueError("Invalid overlap")

    text = text.strip()

    if not text:
        return []

    chunks = []
    step = chunk_size - overlap

    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size]

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(text):
            break

    return chunks


def create_chunks(
    pages: list[ParsedPage],
) -> list[TextChunk]:
    chunks = []

    for page in pages:
        for text in split_text(page.text):
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content=text,
                    page_number=page.number,
                )
            )

    return chunks