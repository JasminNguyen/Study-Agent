"""Vercel entrypoint for creating Managed ChatKit sessions."""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI, Request


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_session


app = FastAPI()


@app.post("/api/create-session")
async def create_session_route(request: Request):
    return await create_session(request)
