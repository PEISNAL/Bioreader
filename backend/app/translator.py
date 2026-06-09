"""
Translation Pipeline — multi-backend with priority fallback.

Priority chain — words (< 50 chars):
  1. FreeDictionary (rich: phonetics, POS, definitions, examples)
  2. BiologyDict (local JSON, sub-millisecond, ~600 terms)
  3. MyMemory (free online API, no key needed)
  4. Ollama (local LLM, optional)
  5. Fallback

Priority chain — sentences (>= 50 chars):
  1. BiologyDict term scan
  2. Ollama paragraph translation
  3. Fallback

Usage:
    from .translator import translate
    result = translate("expression", "gene expression")
    # → TranslateResult(text="expression", translation="表达", phonetic="/ɪkˈsprɛʃən/",
    #     source="dictionary", meanings=[{pos:"noun", defs:[...], examples:[...]}])
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TranslateResult:
    text: str
    translation: str
    phonetic: str = ""
    source: str = "fallback"
    meanings: list[dict] = field(default_factory=list)
    # meanings: [{"pos": "noun", "defs": ["定义1", "定义2"], "examples": ["例句1"], "synonyms": ["syn1"]}]


# ---------------------------------------------------------------------------
# Backend 0: Free Dictionary API (rich English dictionary)
# ---------------------------------------------------------------------------

FREE_DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


class FreeDictionaryBackend:
    """Free English dictionary API — phonetics, POS, definitions, examples, synonyms.

    API docs: https://dictionaryapi.dev/
    No key required. Returns structured word data.
    Only suitable for single words (not phrases/sentences).
    """

    def lookup(self, word: str) -> dict | None:
        """Return rich dictionary entry or None.

        Returns:
            {"phonetic": "/.../", "meanings": [{"pos": "noun", "defs": [...],
             "examples": [...], "synonyms": [...]}]}
        """
        # Only query for single words or short compound terms
        clean = word.strip().lower()
        if not clean or len(clean.split()) > 3 or len(clean) > 60:
            return None

        try:
            import urllib.request
            import urllib.error
            url = FREE_DICT_URL + urllib.parse.quote(clean)
            req = urllib.request.Request(url, headers={"User-Agent": "BioReader/8.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

        if not data or not isinstance(data, list):
            return None

        entry = data[0]
        phonetic = ""
        if entry.get("phonetics"):
            for p in entry["phonetics"]:
                if p.get("text"):
                    phonetic = p["text"]
                    break

        meanings: list[dict] = []
        for m in entry.get("meanings", []):
            pos = m.get("partOfSpeech", "")
            defs = []
            examples = []
            for d in m.get("definitions", []):
                if d.get("definition"):
                    defs.append(d["definition"])
                if d.get("example"):
                    examples.append(d["example"])
            synonyms = m.get("synonyms", [])[:5]
            if defs:
                meanings.append({
                    "pos": pos,
                    "defs": defs[:4],        # cap per POS
                    "examples": examples[:2],
                    "synonyms": synonyms[:5],
                })
            if len(meanings) >= 3:  # cap total POS categories
                break

        if not meanings:
            return None

        return {
            "phonetic": phonetic,
            "meanings": meanings,
        }


# ---------------------------------------------------------------------------
# Backend 1: Embedded Biology Dictionary
# ---------------------------------------------------------------------------


class BiologyDict:
    """In-memory English→Chinese biology terminology dictionary.

    Matching strategy (tried in order):
      1. Exact case-insensitive match
      2. Stemmed match (strip common suffixes: -s, -ed, -ing, -ly, -tion, etc.)
      3. Best substring match (longest dictionary key found in query text)
    """

    _instance: BiologyDict | None = None

    def __new__(cls) -> BiologyDict:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._entries: dict[str, str] = {}
        self._keys_by_length: list[str] = []
        self._load()

    # ---- load ----

    def _load(self) -> None:
        path = os.path.join(os.path.dirname(__file__), "bio_dict.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = data.get("entries", {})
            # sort keys by length descending for best-match substring
            self._keys_by_length = sorted(self._entries.keys(), key=len, reverse=True)
        except Exception:
            self._entries = {}
            self._keys_by_length = []

    # ---- public API ----

    def lookup(self, text: str) -> str | None:
        """Return Chinese translation or None.

        For short text (<80 chars): exact → stemmed → substring match.
        For long text (≥80 chars): scan and extract all known terms.
        """
        if not text or not self._entries:
            return None
        t = text.strip().lower()

        # If query is long (sentence/paragraph), extract known terms
        if len(t) >= 50:
            return self._scan_terms(t)

        # 1) Exact match
        if t in self._entries:
            return self._entries[t]

        # 2) Stemmed match — strip common English suffixes
        stemmed = self._stem(t)
        if stemmed and stemmed in self._entries:
            return self._entries[stemmed]

        # 3) Substring match: dict key inside query text only
        #    (NOT query inside dict key — prevents "expression" matching "ectopic expression")
        for key in self._keys_by_length:
            if key in t:
                return self._entries[key]

        return None

    def _scan_terms(self, text: str) -> str | None:
        """Scan long text for known biology terms; return term→translation pairs."""
        found: dict[str, str] = {}
        lower = text.lower()
        for key in self._keys_by_length:
            if len(key) < 4:  # skip very short keys
                continue
            if key in lower and key not in found:
                found[key] = self._entries[key]
            if len(found) >= 6:  # cap to avoid overwhelming
                break
        if not found:
            return None
        # Format: "term1 → 翻译1; term2 → 翻译2"
        return "；".join(f"{k} → {v}" for k, v in found.items())

    # ---- helpers ----

    @staticmethod
    def _stem(word: str) -> str:
        """Naive stemming: strip common English suffixes."""
        suffixes = [
            "ization", "isation", "ically",
            "ating", "able", "ible", "ally",
            "ness", "ment", "tion", "sion", "ing",
            "ed", "ly", "er", "est", "s", "es",
        ]
        for suf in sorted(suffixes, key=len, reverse=True):
            if word.endswith(suf) and len(word) - len(suf) >= 3:
                return word[: -len(suf)]
        return word

    @property
    def size(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Translation Cache (LRU)
# ---------------------------------------------------------------------------

class TranslationCache:
    """Simple LRU cache for translation results. Avoids repeated network calls."""

    def __init__(self, max_size: int = 500):
        self._max = max_size
        self._store: OrderedDict[str, TranslateResult] = OrderedDict()

    def get(self, key: str) -> TranslateResult | None:
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def put(self, key: str, value: TranslateResult) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        else:
            if len(self._store) >= self._max:
                self._store.popitem(last=False)
            self._store[key] = value

    @staticmethod
    def _make_key(text: str, is_long: bool) -> str:
        t = text.strip().lower()
        return f"{'L' if is_long else 'W'}:{t[:80]}"


# ---------------------------------------------------------------------------
# Backend 2: Ollama (local LLM)
# ---------------------------------------------------------------------------


class OllamaBackend:
    """Local LLM translation via Ollama.

    Auto-detects availability at startup. Uses same prompt style as original.
    """

    OLLAMA_URL = "http://localhost:11434/api/chat"
    DEFAULT_MODEL = "qwen2.5:3b"

    PROMPT_WORD = (
        "You are an academic English-Chinese translator. "
        "Translate the given word or phrase with its context. "
        "Output STRICT JSON: {\"translation\":\"中文释义\",\"phonetic\":\"音标或读音提示\"}"
    )

    PROMPT_PARA = (
        "You are an academic English-Chinese translator specializing in biology. "
        "Translate the following English text into fluent, accurate Chinese. "
        "Preserve the academic tone and technical accuracy. "
        "Output STRICT JSON: {\"translation\":\"中文翻译全文\",\"phonetic\":\"\"}"
    )

    def __init__(self) -> None:
        self._available: bool | None = None
        self._model: str = self.DEFAULT_MODEL

    # ---- availability ----

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = self._detect()
        return self._available

    def _detect(self) -> bool:
        try:
            import httpx
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return len(models) > 0
        except Exception:
            pass
        return False

    # ---- translate ----

    def translate(self, text: str, context: str = "") -> dict | None:
        if not self.available:
            return None

        # Choose prompt based on text length
        is_long = len(text) > 120
        system_prompt = self.PROMPT_PARA if is_long else self.PROMPT_WORD
        max_tokens = 600 if is_long else 200

        prompt = f'Translate: "{text}"'
        if context and not is_long:
            prompt += f"\nContext: {context[:300]}"

        try:
            import httpx
            resp = httpx.post(
                self.OLLAMA_URL,
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": max_tokens},
                },
                timeout=30,
            )
            if resp.status_code != 200:
                return None

            content = resp.json()["message"]["content"]
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                return json.loads(m.group(0))
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Translation Pipeline
# ---------------------------------------------------------------------------


class TranslationPipeline:
    """Orchestrate multiple backends with priority fallback + caching.

    Words (< 50 chars): Cache → FreeDict → BioDict → Ollama
    Sentences (>= 50 chars): Cache → Ollama → BioDict term scan
    """

    def __init__(self) -> None:
        self._cache = TranslationCache(max_size=500)
        self._freedict = FreeDictionaryBackend()
        self._dict = BiologyDict()
        self._ollama = OllamaBackend()

    def translate(self, text: str, context: str = "") -> TranslateResult:
        """Run backends in priority order; cache-first."""
        is_long = len(text) >= 50
        cache_key = f"{'L' if is_long else 'W'}:{text.strip().lower()[:80]}"

        cached = self._cache.get(cache_key)
        if cached:
            return cached

        if not is_long:
            result = self._translate_word(text, context)
        else:
            result = self._translate_sentence(text)

        self._cache.put(cache_key, result)
        return result

    def _translate_word(self, text: str, context: str) -> TranslateResult:
        """Word-level pipeline: FreeDict → BioDict → Ollama (with fast timeouts)."""
        all_meanings: list[dict] = []
        phonetic = ""

        # Backend 0: Free Dictionary API (richest, 3s timeout)
        fd_result = self._freedict.lookup(text)
        if fd_result:
            phonetic = fd_result.get("phonetic", "")
            all_meanings = fd_result.get("meanings", [])

        # Backend 1: Biology Dictionary (instant, in-memory)
        bio_result = self._dict.lookup(text)
        bio_translation = ""
        if bio_result:
            bio_translation = bio_result
            if not all_meanings:
                all_meanings = [{"pos": "biology", "defs": [bio_result], "examples": [], "synonyms": []}]
            else:
                if not any(bio_result in d.get("defs", []) for d in all_meanings):
                    all_meanings[0]["defs"].insert(0, f"[生物学] {bio_result}")

        # Primary translation
        if bio_translation:
            translation = bio_translation
            source = "dictionary"
        elif all_meanings:
            translation = all_meanings[0]["defs"][0] if all_meanings[0].get("defs") else text
            source = "dictionary"
        else:
            translation = ""

        if translation:
            return TranslateResult(
                text=text, translation=translation, phonetic=phonetic,
                source=source, meanings=all_meanings,
            )

        # Backend 2: Ollama (fallback for words not in any dictionary)
        ollama_result = self._ollama.translate(text, context)
        if ollama_result and ollama_result.get("translation"):
            return TranslateResult(
                text=text,
                translation=ollama_result["translation"],
                phonetic=ollama_result.get("phonetic", phonetic),
                source="ollama",
                meanings=all_meanings,
            )

        return TranslateResult(text=text, translation=text, phonetic=phonetic,
                               source="fallback", meanings=all_meanings)

    def _translate_sentence(self, text: str) -> TranslateResult:
        """Sentence/paragraph pipeline: Ollama → BioDict term scan fallback."""
        # Backend 1: Ollama paragraph translation
        ollama_result = self._ollama.translate(text, "")
        if ollama_result and ollama_result.get("translation"):
            return TranslateResult(
                text=text, translation=ollama_result["translation"],
                phonetic="", source="ollama",
            )

        # Backend 2: BioDict term scan
        bio_result = self._dict.lookup(text)
        if bio_result:
            return TranslateResult(
                text=text, translation=bio_result, source="dictionary",
            )

        return TranslateResult(text=text, translation=text, source="fallback")


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_pipeline: TranslationPipeline | None = None


def translate(text: str, context: str = "") -> TranslateResult:
    """One-shot translation with all backends. Safe to call from any thread."""
    global _pipeline
    if _pipeline is None:
        _pipeline = TranslationPipeline()
    return _pipeline.translate(text, context)


def dict_size() -> int:
    """Return the number of entries in the embedded dictionary."""
    return BiologyDict().size
