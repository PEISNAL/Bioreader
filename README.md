# 🧬 BioReader

**AI-powered academic paper reader** — upload any biology PDF, read with real-time translation, vocabulary tracking, and synchronized figure display.

![Version](https://img.shields.io/badge/version-9.0-blue)
![Python](https://img.shields.io/badge/python-3.13+-green)
![TypeScript](https://img.shields.io/badge/typescript-5.x-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

### 📄 Universal PDF Parsing
- **Drag-and-drop upload** — any biology journal PDF, auto-parsed on upload
- **Geometry-based cleaning** — auto-detects and removes headers, footers, page numbers, DOIs, and footnote cruft across all pages (no per-journal hardcoding)
- **Multi-strategy reference parsing** — handles numbered, author-year, and mixed citation formats
- **Figure extraction** — PyMuPDF direct image extraction with caption matching

### 🌐 Intelligent Translation (Multi-Backend Pipeline)
| Priority | Backend | Speed | Best For |
|----------|---------|-------|----------|
| 1 | **Free Dictionary API** | ~1s | Words — phonetics, POS, multiple definitions, examples |
| 2 | **BioDict** (613 terms) | <1ms | Biology terminology — instant offline lookup |
| 3 | **Ollama** (local LLM) | ~3-10s | Sentences & paragraphs — full academic translation |
| 4 | **Translation Cache** (LRU 500) | <1ms | Repeat queries — zero network overhead |

- Select any text (word → phrase → sentence → paragraph) and translate
- Rich dictionary display: phonetic transcription, part-of-speech tags, numbered definitions, usage examples, synonyms
- Sentence translation: full paragraph rendering with academic tone preservation
- Source label shows which backend served the result

### 📖 Vocabulary Book
- Save words with full dictionary data (phonetic, POS, definitions, examples)
- Collapsible side panel — minimize to 40px strip when not in use
- Persistent JSON storage
- Search and delete entries

### 🖼️ Figure Sync
- Figures extracted directly from PDF pages via PyMuPDF
- Right-side panel shows all figures with captions
- Scroll-sync highlighting — active figure lights up as you read
- Lazy-loaded images with page number indicators

### 📚 Clean Reference Display
- Auto-numbered `[1]` `[2]` `[3]` format
- Alternating background for readability
- Clear line separation between entries

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React + TS)             │
│  Drag-drop upload → Reader view → Translation popup  │
│  Vocab drawer ↔ Figure panel ↔ Reference list        │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (JSON)
┌──────────────────────┴──────────────────────────────┐
│                Backend (FastAPI + Python)             │
│                                                      │
│  /api/upload   →  parser.py (S1-S5 pipeline)         │
│  /api/translate →  translator.py (multi-backend)     │
│  /api/vocabulary → vocab.py (JSON persistence)       │
│                                                      │
│  S1: Symbol normalization                            │
│  S2: Universal margin filter + page header removal   │
│  S3: Section parsing + figure caption extraction     │
│  S4: Multi-strategy reference parsing                │
│  S5: Figure image extraction (PyMuPDF)               │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                  External Services                    │
│  Free Dictionary API  │  Ollama (local LLM)          │
│  dictionaryapi.dev     │  localhost:11434             │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`
- **Ollama** (optional — for sentence/paragraph translation)

### 1. Clone
```bash
git clone https://github.com/PEISNAL/Bioreader.git
cd Bioreader
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 18000
```

### 3. Frontend
```bash
cd frontend
npm install
npx vite --host 127.0.0.1 --port 5173
```

### 4. (Optional) Ollama for sentence translation
```bash
ollama pull qwen2.5:3b
```

### 5. Open
Navigate to **http://127.0.0.1:5173** — drag a PDF onto the upload zone.

---

## 📁 Project Structure

```
Bioreader/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI application + endpoints
│   │   ├── parser.py         # S1-S5 PDF parsing pipeline
│   │   ├── translator.py     # Multi-backend translation engine
│   │   ├── vocab.py          # Vocabulary JSON persistence
│   │   └── bio_dict.json     # 613-entry biology term dictionary
│   ├── static/figures/       # Extracted figure images
│   ├── uploads/              # Uploaded PDFs (gitignored)
│   ├── vocabulary.json       # User vocabulary data
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── App.tsx           # Full React application (single-file)
│   ├── package.json
│   └── vite.config.ts
├── test.pdf                  # Sample test paper
└── README.md
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| PDF Parsing | PyMuPDF (`fitz`), `pymupdf4llm` |
| Backend Framework | FastAPI + Pydantic v2 |
| Translation | Free Dictionary API, Ollama (qwen2.5:3b) |
| Frontend | React 18 + TypeScript, Vite |
| Styling | Inline CSS (zero dependencies) |
| Storage | JSON file persistence |

---

## 🔧 Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `OLLAMA_POLISH` | (unset) | Enable LLM paragraph polishing during parse (S5) |

---

## 📝 Translation Examples

### Single word — rich dictionary
```
Input:  "expression"
Output: phonetic: /ɪkˈsprɛʃ.ən/
        [noun] 1. The action of expressing thoughts, ideas, feelings, etc.
               2. A particular way of phrasing an idea.
               e.g. "The expression 'break a leg!' should not be taken literally."
        [biology] 异位表达
Source: 📖 词典
```

### Biology term — instant offline
```
Input:  "methylation"
Output: 甲基化
Source: 📖 词典 (613-term BioDict, <1ms)
```

### Sentence — AI translation
```
Input:  "DNA methylation plays a critical role in gene silencing
         and epigenetic regulation of transcription"
Output: DNA甲基化在基因沉默和转录的表观遗传调控中起着关键作用
Source: 🤖 AI (Ollama)
```

---

## 📄 License

MIT License

---

**Built for biologists, by biologists.** 🧬
