"""Vercel entrypoint for extracting text from uploaded documents."""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI, File, UploadFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import upload_document


app = FastAPI()


@app.post("/api/upload-document")
async def upload_document_route(file: UploadFile = File(...)):
    return await upload_document(file)
