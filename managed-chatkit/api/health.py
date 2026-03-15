"""Vercel health check endpoint for Managed ChatKit."""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import health


app = FastAPI()


@app.get("/api/health")
async def health_route():
    return await health()
