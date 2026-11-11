import json
from pathlib import Path


def load_dataset(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [q["id"] for q in data["questions"]]
    assert len(ids) == len(set(ids)), "Дубликаты id вопросов"
    for q in data["questions"]:
        assert q["question"].strip(), f"{q['id']}: пустой вопрос"
        if q["type"] != "unanswerable":
            assert q["evidence"], f"{q['id']}: нет evidence"
    return data