"""FastAPI entrypoint for document upload and retrieval chat."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Mapping, Sequence

import httpx
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.vector_store import create_user_vector_store

DEFAULT_CHATKIT_BASE = "https://api.openai.com"
SESSION_COOKIE_NAME = "chatkit_session_id"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
SUPPORTED_DOCUMENT_TYPES = {".txt", ".md", ".pdf", ".docx"}
DEFAULT_CHAT_MODEL = "gpt-4.1-mini"

app = FastAPI(title="Managed ChatKit Session API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Mapping[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(request: Request) -> JSONResponse:
    """Answer a user question using file search over an uploaded document."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return respond({"error": "Missing OPENAI_API_KEY environment variable"}, 500)

    body = await read_json_body(request)
    message = read_non_empty_string(body.get("message"))
    vector_store_id = read_non_empty_string(body.get("vector_store_id"))
    history = normalize_chat_history(body.get("history"))

    if not vector_store_id:
        return respond({"error": "Missing vector_store_id"}, 400)
    if not message:
        return respond({"error": "Missing message"}, 400)

    user_id, cookie_value = resolve_user(request.cookies)
    api_base = responses_api_base()
    model = os.getenv("OPENAI_CHAT_MODEL") or DEFAULT_CHAT_MODEL
    prompt = build_chat_prompt(history, message)

    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
            upstream = await client.post(
                "/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": prompt,
                    "instructions": (
                        "Use file search results as the primary source. "
                        "Answer clearly and say when the document does not contain the answer."
                    ),
                    "tools": [
                        {
                            "type": "file_search",
                            "vector_store_ids": [vector_store_id],
                            "max_num_results": 8,
                        }
                    ],
                    "metadata": {"chat_session_user": user_id},
                },
            )
    except httpx.RequestError as error:
        return respond(
            {"error": f"Failed to reach OpenAI Responses API: {error}"},
            502,
            cookie_value,
        )

    payload = parse_json(upstream)
    if not upstream.is_success:
        error_message = None
        if isinstance(payload, Mapping):
            error_payload = payload.get("error")
            if isinstance(error_payload, Mapping):
                error_message = read_non_empty_string(error_payload.get("message"))
            elif isinstance(error_payload, str):
                error_message = error_payload
        error_message = error_message or upstream.reason_phrase or "Failed to create response"
        return respond({"error": error_message}, upstream.status_code, cookie_value)

    answer = extract_response_text(payload)
    if not answer:
        return respond({"error": "Missing text in model response"}, 502, cookie_value)

    return respond(
        {"answer": answer},
        200,
        cookie_value,
    )


@app.post("/api/upload-document")
async def upload_document(file: UploadFile = File(...)) -> JSONResponse:
    """Create a vector store from a supported uploaded document."""
    filename = (file.filename or "").strip()
    extension = file_extension(filename)

    if extension not in SUPPORTED_DOCUMENT_TYPES:
        return respond(
            {
                "error": "Unsupported file type. Upload a .txt, .md, .pdf, or .docx file."
            },
            400,
        )

    content = await file.read()
    if not content:
        return respond({"error": "Uploaded file is empty."}, 400)

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        return respond(
            {"error": "Uploaded file is too large. Maximum size is 25 MB."},
            400,
        )

    try:
        vector_store_id = create_user_vector_store(
            content,
            filename or f"document{extension}",
        )
    except Exception:
        return respond(
            {"error": "We couldn't upload that file to the vector store right now."},
            502,
        )

    return respond(
        {
            "filename": filename or f"document{extension}",
            "vector_store_id": vector_store_id,
        },
        200,
    )


def respond(
    payload: Mapping[str, Any], status_code: int, cookie_value: str | None = None
) -> JSONResponse:
    response = JSONResponse(payload, status_code=status_code)
    if cookie_value:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=cookie_value,
            max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=is_prod(),
            path="/",
        )
    return response


def is_prod() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("NODE_ENV") or "").lower()
    return env == "production"


async def read_json_body(request: Request) -> Mapping[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def resolve_user(cookies: Mapping[str, str]) -> tuple[str, str | None]:
    existing = cookies.get(SESSION_COOKIE_NAME)
    if existing:
        return existing, None
    user_id = str(uuid.uuid4())
    return user_id, user_id


def responses_api_base() -> str:
    return (
        os.getenv("CHATKIT_API_BASE")
        or os.getenv("VITE_CHATKIT_API_BASE")
        or DEFAULT_CHATKIT_BASE
    )


def parse_json(response: httpx.Response) -> Mapping[str, Any]:
    try:
        parsed = response.json()
        return parsed if isinstance(parsed, Mapping) else {}
    except (json.JSONDecodeError, httpx.DecodingError):
        return {}


def file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return f".{filename.rsplit('.', 1)[-1].lower()}"


def read_non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def normalize_chat_history(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []

    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        role = read_non_empty_string(item.get("role"))
        content = read_non_empty_string(item.get("content"))
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def build_chat_prompt(history: list[dict[str, str]], message: str) -> str:
    transcript: list[str] = []
    for entry in history[-8:]:
        speaker = "User" if entry["role"] == "user" else "Assistant"
        transcript.append(f"{speaker}: {entry['content']}")

    transcript.append(f"User: {message}")
    transcript.append(
        "Assistant: Answer the user's latest question using the uploaded document."
    )
    return "\n".join(transcript)


def extract_response_text(payload: Mapping[str, Any]) -> str | None:
    direct_text = read_non_empty_string(payload.get("output_text"))
    if direct_text:
        return direct_text

    output = payload.get("output")
    if not isinstance(output, Sequence):
        return None

    text_fragments: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, Sequence):
            continue
        for part in content:
            if not isinstance(part, Mapping):
                continue
            text_value = read_non_empty_string(part.get("text"))
            if text_value:
                text_fragments.append(text_value)

    if not text_fragments:
        return None
    return "\n".join(text_fragments)
