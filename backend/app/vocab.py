"""Vocabulary store — JSON file persistence."""
import json, os, time
from typing import Any

DB = os.path.join(os.path.dirname(__file__), "..", "vocabulary.json")

def _load() -> list[dict]:
    if not os.path.exists(DB):
        return []
    with open(DB, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: list[dict]) -> None:
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add(word: str, context: str = "", translation: str = "", section: str = "",
        phonetic: str = "", meanings: list = None) -> dict:
    data = _load()
    if meanings is None:
        meanings = []
    # Update or insert
    for item in data:
        if item["word"].lower() == word.lower():
            item["context"] = context or item.get("context", "")
            item["translation"] = translation or item.get("translation", "")
            item["section"] = section or item.get("section", "")
            item["phonetic"] = phonetic or item.get("phonetic", "")
            item["meanings"] = meanings or item.get("meanings", [])
            item["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save(data)
            return item
    entry = {
        "word": word,
        "context": context,
        "translation": translation,
        "section": section,
        "phonetic": phonetic,
        "meanings": meanings,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    data.append(entry)
    _save(data)
    return entry

def list_all() -> list[dict]:
    return sorted(_load(), key=lambda x: x.get("timestamp", ""), reverse=True)

def remove(word: str) -> bool:
    data = _load()
    new = [d for d in data if d["word"].lower() != word.lower()]
    if len(new) < len(data):
        _save(new)
        return True
    return False
