import re
from dataclasses import dataclass

from app.services.document_parser import ParsedPage


CHUNK_SIZE = 600
CHUNK_OVERLAP = 120

MAX_HEADING_LEN = 100
_TERMINAL = (".", "!", "?", "…", ":", ";")
_NOT_HEADING_END = _TERMINAL + (",",)
_BULLETS = ("-", "•", "*", "–", "—")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЁ0-9«\"(])")


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    page_number: int | None


def _is_heading(line: str) -> bool:
    if len(line) > MAX_HEADING_LEN or line.endswith(_NOT_HEADING_END):
        return False
    if line.startswith(_BULLETS):
        return False
    return line[0].isupper() or line[0].isdigit()


def _join_wrapped(lines: list[str]) -> list[str]:
    """Склеивает строки, перенесённые по ширине страницы (типично для PDF)."""
    out: list[str] = []
    for line in lines:
        if out and not out[-1].endswith(_TERMINAL) and line[0].islower():
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _to_units(text: str) -> list[str]:
    """Текст -> предложения; заголовок остаётся с первым предложением раздела."""
    units: list[str] = []
    heading = ""

    for paragraph in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in paragraph.splitlines() if ln.strip()]

        for line in _join_wrapped(lines):
            if _is_heading(line):
                heading = f"{heading}\n{line}" if heading else line
                continue

            for sentence in _SENTENCE_SPLIT.split(line):
                sentence = sentence.strip()
                if not sentence:
                    continue
                units.append(f"{heading}\n{sentence}" if heading else sentence)
                heading = ""

    if heading:
        units.append(heading)

    return units


def _split_long(unit: str, size: int) -> list[str]:
    """Режет слишком длинный фрагмент по границам слов."""
    if len(unit) <= size:
        return [unit]

    pieces: list[str] = []
    current = ""

    for word in unit.split(" "):
        while len(word) > size:  # одно «слово» длиннее лимита (URL и т.п.)
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:size])
            word = word[size:]

        if not current:
            current = word
        elif len(current) + 1 + len(word) <= size:
            current = f"{current} {word}"
        else:
            pieces.append(current)
            current = word

    if current:
        pieces.append(current)

    return pieces


def _carry_overlap(units: list[str], overlap: int) -> tuple[list[str], int]:
    """Хвост предыдущего чанка из целых предложений длиной не больше overlap."""
    tail: list[str] = []
    total = 0
    for unit in reversed(units):
        added = len(unit) + (1 if tail else 0)
        if total + added > overlap:
            break
        tail.insert(0, unit)
        total += added
    return tail, total


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Нарезка по предложениям: границы чанков совпадают с границами предложений."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if not 0 <= overlap < chunk_size:
        raise ValueError("Invalid overlap")

    text = text.replace("\r\n", "\n").strip()

    if not text:
        return []

    chunks: list[str] = []
    current: list[str] = []
    length = 0

    for unit in _to_units(text):
        for piece in _split_long(unit, chunk_size):
            added = len(piece) + (1 if current else 0)

            if current and length + added > chunk_size:
                chunks.append(" ".join(current))
                current, length = _carry_overlap(current, overlap)
                added = len(piece) + (1 if current else 0)

                if current and length + added > chunk_size:
                    current, length = [], 0  # перекрытие не помещается
                    added = len(piece)

            current.append(piece)
            length += added

    if current:
        chunks.append(" ".join(current))

    return chunks


def split_text_fixed(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[str]:
    """Оригинальная нарезка по числу символов (для сравнения в экспериментах)."""
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
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    strategy: str = "sentence",
) -> list[TextChunk]:
    if strategy == "sentence":
        splitter = split_text
    elif strategy == "fixed":
        splitter = split_text_fixed
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")

    chunks = []

    for page in pages:
        for text in splitter(page.text, chunk_size, overlap):
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content=text,
                    page_number=page.number,
                )
            )

    return chunks
