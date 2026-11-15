from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from pdf_stand.pipeline import parse_file

app = FastAPI(title="pdf-stand", version="0.1.0")
MAX_BYTES = 25 * 1024 * 1024


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse")
async def parse(file: UploadFile = File(...)) -> dict:
    name = file.filename or "upload.pdf"
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="expected a .pdf file")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"file too large (max {MAX_BYTES} bytes)")

    with tempfile.TemporaryDirectory(prefix="pdf-stand-api-") as tmp:
        path = Path(tmp) / Path(name).name
        path.write_bytes(raw)
        return parse_file(path).to_dict()
