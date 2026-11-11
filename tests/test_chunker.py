import pytest

from app.services.chunker import split_text, split_text_fixed

TEXT = (
    "Заголовок документа\n\n"
    "1. Даты\n"
    "Хакатон проходит в марте. Регистрация открыта до февраля. Новые команды не принимаются.\n\n"
    "2. Выступление\n"
    "Каждая команда выступает 7 минут. Затем жюри задаёт вопросы 3 минуты. Презентация должна содержать демо."
)

SENT = [f"Предложение номер {i} закончено." for i in range(1, 9)]
SENT_TEXT = " ".join(SENT)


def test_empty_text():
    assert split_text("  \n ") == []


def test_invalid_params():
    with pytest.raises(ValueError):
        split_text("x", chunk_size=0)
    with pytest.raises(ValueError):
        split_text("x", chunk_size=10, overlap=10)


def test_chunks_never_exceed_size():
    chunks = split_text(TEXT, chunk_size=90, overlap=0)
    assert all(len(c) <= 90 for c in chunks)


def test_no_word_is_cut():
    original = set(TEXT.split())
    for chunk in split_text(TEXT, chunk_size=90, overlap=0):
        assert set(chunk.split()) <= original


def test_heading_stays_with_its_text():
    chunks = split_text(TEXT, chunk_size=90, overlap=0)
    with_heading = [c for c in chunks if "2. Выступление" in c]
    assert len(with_heading) == 1
    assert "Каждая команда" in with_heading[0]


def test_overlap_repeats_whole_sentence():
    chunks = split_text(SENT_TEXT, chunk_size=90, overlap=35)
    assert len(chunks) > 1
    for a, b in zip(chunks, chunks[1:]):
        last = max((s for s in SENT if s in a), key=SENT.index)
        assert last in b


def test_zero_overlap_has_no_repeats():
    chunks = split_text(SENT_TEXT, chunk_size=90, overlap=0)
    for a, b in zip(chunks, chunks[1:]):
        assert not ({s for s in SENT if s in a} & {s for s in SENT if s in b})


def test_very_long_word_is_split():
    chunks = split_text("а" * 250, chunk_size=100, overlap=0)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == "а" * 250


def test_fixed_strategy_keeps_original_behavior():
    chunks = split_text_fixed("a" * 2500, chunk_size=1000, overlap=150)
    assert [len(c) for c in chunks] == [1000, 1000, 800]
