"""BioReader Backend"""
import os, time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .parser import parse

class ParseReq(BaseModel):
    file_path: str = Field(..., description="PDF absolute path")

app = FastAPI(title="BioReader API", version="6.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "ok", "version": "6.0.0"}

@app.post("/api/parse")
async def parse_pdf(req: ParseReq):
    if not os.path.isfile(req.file_path):
        raise HTTPException(404, "File not found")
    return {"file_path": req.file_path, **parse(req.file_path)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18000)
