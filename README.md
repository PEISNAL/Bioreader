# 🧬 BioReader

**AI-powered academic paper reader** — upload any biology PDF, read with real-time translation, vocabulary tracking, and synchronized figure display.

![Version](https://img.shields.io/badge/version-9.2-blue)
![Python](https://img.shields.io/badge/python-3.13+-green)
![TypeScript](https://img.shields.io/badge/typescript-5.x-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

### 📄 Universal PDF Parsing
- **Drag-and-drop upload** — any journal PDF, auto-parsed on upload
- **Geometry-based header/footer removal** — auto-detects running titles, page numbers, journal names, DOIs across all pages via PyMuPDF cross-page analysis
- **Page header stripping** — removes pymupdf4llm-inserted running titles between paragraphs
- **Multi-strategy reference parsing** — DOI-boundary split, bullet-list, numbered-list, author-year, and fallback patterns. Handles any journal format.
- **Figure image extraction** — PyMuPDF pixmap rendering at full resolution, auto-cleaned per upload

### 🌐 Intelligent Translation (Multi-Backend Pipeline)
| Priority | Backend | Speed | Best For |
|----------|---------|-------|----------|
| 1 | **Free Dictionary API** | ~1s | Words — phonetics, POS, multiple definitions, examples, synonyms |
| 2 | **BioDict** (613 terms) | <1ms | Biology terminology — instant offline lookup |
| 3 | **Ollama** (local LLM) | ~3-10s | Sentences & paragraphs — full academic translation |
| 4 | **Translation Cache** (LRU 500) | <1ms | Repeat queries — zero network overhead |

- Select any text (word → phrase → sentence → paragraph up to 2000 chars)
- Rich dictionary display: phonetic, POS tags, numbered definitions, usage examples, synonyms
- Sentence/paragraph AI translation with academic tone preservation
- Source label shows which backend served the result

### 📖 Smart Vocabulary Book
- **Dedicated full-page view** — navigate from reader topbar
- Saves complete dictionary data: phonetic, POS, definitions, examples, synonyms
- Delete entries individually
- Persistent JSON storage

### 🖼️ Figure Panel & Sync
- **Inline figure buttons** — `📊 Figure N` buttons inserted directly in paragraph text at every `Figure N` / `Fig. N` mention
- **Click to highlight** — figure card in side panel gets blue glow + pulse animation
- **Click card to enlarge** — fullscreen modal with large image + caption
- **Scroll sync** — IntersectionObserver auto-highlights figure as you read past its reference
- **Flexible panel** — fills right side, max 420px width
- PNG images rendered via PyMuPDF pixmap at full quality

### 📚 Clean Reference Display
- Auto-numbered `[1]` `[2]` `[3]` monospace format
- Blue left border, alternating background, clear 14px spacing
- 5-tier split strategy ensures clean extraction from any journal

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                Frontend (React 18 + TS + Vite)       │
│  Drag-drop → Reader → Translation popup              │
│  Vocab page ↔ Figure panel ↔ Reference list          │
│  Vite proxy: /api/* → backend :18000                 │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (JSON)
┌──────────────────────┴──────────────────────────────┐
│              Backend (FastAPI + Python 3.13)          │
│                                                      │
│  /api/upload    → parser.py (S1-S5 pipeline)         │
│  /api/translate → translator.py (multi-backend)      │
│  /api/vocabulary→ vocab.py (JSON persistence)        │
│  /api/figures/  → FileResponse (CORS-safe images)    │
│                                                      │
│  S1: Symbol normalization                            │
│  S2: Universal margin filter + page header removal   │
│  S3: Section parsing + figure caption extraction     │
│  S4: Multi-strategy reference parsing                │
│  S5: Figure image extraction (PyMuPDF pixmap)        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                External Services                      │
│  Free Dictionary API   │  Ollama (local LLM)         │
│  api.dictionaryapi.dev  │  localhost:11434            │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Ollama (optional, for AI sentence translation)

### 1. Clone & Install
```bash
git clone https://github.com/PEISNAL/Bioreader.git
cd Bioreader

# Backend
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Run
```bash
# Terminal 1 — Backend (port 18000)
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 18000

# Terminal 2 — Frontend (port 5173)
cd frontend
npx vite --host 127.0.0.1 --port 5173
```

### 3. (Optional) Install Ollama for AI translation
```bash
ollama pull qwen2.5:3b
```

### 4. Open
Navigate to **http://127.0.0.1:5173** — drag a PDF onto the upload zone.

---

## 📁 Project Structure

```
Bioreader/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app + all endpoints
│   │   ├── parser.py         # S1-S5 PDF parsing pipeline
│   │   ├── translator.py     # Multi-backend translation engine + cache
│   │   ├── vocab.py          # Vocabulary JSON persistence
│   │   └── bio_dict.json     # 613-entry biology EN→ZH dictionary
│   ├── static/figures/       # Extracted figure images (auto-cleaned)
│   ├── uploads/              # Uploaded PDFs (gitignored)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── App.tsx           # Full React app (single-file)
│   ├── vite.config.ts        # Vite + /api proxy
│   └── package.json
└── README.md
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| PDF Parsing | PyMuPDF (`fitz`), `pymupdf4llm` |
| Backend | FastAPI + Pydantic v2 |
| Translation | Free Dictionary API, Ollama (qwen2.5:3b) |
| Frontend | React 18 + TypeScript, Vite 5 |
| Styling | Inline CSS (zero-dependency) |
| Storage | JSON file persistence |

---

## 📝 Examples

### Word — rich dictionary
```
Input:  "expression"
Phonetic: /ɪkˈsprɛʃ.ən/
[noun]  1. The action of expressing thoughts, ideas, feelings, etc.
        2. A particular way of phrasing an idea.
        e.g. "The expression 'break a leg!' should not be taken literally."
[biology] 异位表达
Source: 📖 词典
```

### Biology term — instant offline
```
Input:  "methylation"   →   甲基化   (<1ms, BioDict)
```

### Sentence — AI translation
```
Input:  "DNA methylation plays a critical role in gene silencing
         and epigenetic regulation of transcription"
Output: DNA甲基化在基因沉默和转录的表观遗传调控中起着关键作用
Source: 🤖 AI (Ollama)
```

### Figure interaction
```
Click "📊 Figure 1" in text → side panel scrolls + highlights Figure 1
Click figure card in panel → fullscreen enlarged view with caption
```

---

## 🔧 Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `OLLAMA_POLISH` | (unset) | Enable LLM paragraph polishing during parse |

---

## 📄 License

MIT

---

**Built for biologists, by biologists.** 🧬
