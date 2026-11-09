from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pymupdf
from docx import Document


@dataclass(frozen=True)
class ParsedPage:
    number: int | None
    text: str


def parse_document(
    filename: str,
    content: bytes,
) -> list[ParsedPage]:
    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return parse_pdf(content)

    if extension == ".docx":
        return parse_docx(content)

    if extension == ".txt":
        return parse_txt(content)

    raise ValueError("Unsupported file format")


def parse_pdf(content: bytes) -> list[ParsedPage]:
    pages = []

    with pymupdf.open(
        stream=content,
        filetype="pdf",
    ) as document:
        for index, page in enumerate(document):
            text = page.get_text("text", sort=True)

            if text.strip():
                pages.append(
                    ParsedPage(
                        number=index + 1,
                        text=text,
                    )
                )

    return pages


def parse_docx(content: bytes) -> list[ParsedPage]:
    document = Document(BytesIO(content))

    parts = []

    for item in document.iter_inner_content():
        if item.__class__.__name__ == "Paragraph":
            if item.text.strip():
                parts.append(item.text)
        else:
            for row in item.rows:
                cells = [cell.text for cell in row.cells]
                parts.append(" | ".join(cells))

    return [
        ParsedPage(
            number=None,
            text="\n".join(parts),
        )
    ]


def parse_txt(content: bytes) -> list[ParsedPage]:
    text = content.decode("utf-8-sig")

    return [
        ParsedPage(
            number=None,
            text=text,
        )
    ]