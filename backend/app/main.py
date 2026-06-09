"""BioReader Backend — FastAPI"""
import os, uuid, shutil
from typing import Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .parser import parse
from .vocab import add, list_all, remove

# ---- Models ----
class ParseReq(BaseModel):
    file_path: str = Field(..., description="PDF absolute path")

class VocabAdd(BaseModel):
    word: str
    context_sentence: str = ""
    translation: str = ""
    section_title: str = ""
    phonetic: str = ""
    meanings: list[dict[str, Any]] = []

class TranslateReq(BaseModel):
    text: str
    context: str = ""

# ---- App ----
app = FastAPI(title="BioReader API", version="7.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Static files for figure images
os.makedirs("static/figures", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "7.1.0"}

# ---- Parse ----
@app.post("/api/parse")
async def parse_pdf(req: ParseReq):
    if not os.path.isfile(req.file_path):
        raise HTTPException(404, "File not found")
    return {"file_path": req.file_path, **parse(req.file_path)}

# ---- Upload ----
@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    file_id = uuid.uuid4().hex[:8]
    safe_name = file.filename.replace(" ", "_")
    save_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "file_path": save_path, **parse(save_path)}

# ---- Vocabulary ----
@app.post("/api/vocabulary")
async def add_vocab(req: VocabAdd):
    entry = add(req.word, req.context_sentence, req.translation, req.section_title,
                req.phonetic, req.meanings)
    return {"status": "ok", "entry": entry}

@app.get("/api/vocabulary")
async def list_vocab():
    return {"words": list_all()}

@app.delete("/api/vocabulary/{word}")
async def delete_vocab(word: str):
    if remove(word):
        return {"status": "deleted", "word": word}
    raise HTTPException(404, "Word not found")

# ---- Figure Images (CORS-safe) ----
@app.get("/api/figures/{name}")
async def get_figure(name: str):
    path = os.path.join("static", "figures", name)
    if not os.path.exists(path):
        raise HTTPException(404, "Figure not found")
    return FileResponse(path, media_type="image/png")

# ---- Translate (multi-backend pipeline) ----
from .translator import translate as translate_text

@app.post("/api/translate")
async def translate(req: TranslateReq):
    result = translate_text(req.text, req.context)
    return {
        "text": result.text,
        "translation": result.translation,
        "phonetic": result.phonetic,
        "source": result.source,
        "meanings": result.meanings,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18000)
