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
INTENT_LABELS = {"qa", "explain", "plan", "quiz"}

IDENTIFIER_PROMPT = """You are an identifier agent for a study assistant.
Classify the user's latest request into exactly one label:
- qa: the user wants factual answers grounded in the document
- explain: the user wants a concept explained simply
- plan: the user wants a study plan or schedule
- quiz: the user wants quiz questions, review questions, or answer evaluation

Use the recent conversation for context. Reply with only one lowercase label:
qa, explain, plan, or quiz."""

QA_PROMPT = """You are a document analysis assistant.
Use the uploaded documents available through file search. These documents may vary between sessions. Always retrieve relevant passages before giving an answer.

Your task is to answer the user's question using the retrieved passages from the uploaded document(s).
Rules:
1) Treat the retrieved passages as the primary source of truth.
2) Base your answer only on the provided document content whenever possible.
3) If the answer is not clearly supported by the retrieved passages, say: "I cannot find a clear answer in the provided document."
4) Do not invent facts that are not present in the document.
5) When useful, quote short excerpts from the passages to support your answer.
6) If possible, mention the section, chapter, or page where the information appears.
7) Keep the answer concise, structured, and factual.

Output format:
Answer

Evidence

Notes (optional)"""

EXPLAIN_PROMPT = """You are a study assistant helping the user understand difficult concepts in the document.
Use the uploaded documents available through file search. These documents may vary between sessions. Always retrieve relevant passages before giving an answer.
Use the retrieved document passages as the foundation of your explanation.
Steps:
Identify the concept or term referenced in the document.
Briefly explain what the document says about it.
Provide a clear and simple explanation in plain language.
If helpful, include a short example or analogy.
Distinguish clearly between:
what the document states
your general explanation.
Rules:
1) Do not contradict the document.
2) Do not invent claims about the document that are not supported by the retrieved passages. If the retrieved passages do not contain the answer, respond that the information is not present in the uploaded document.
3) Keep explanations clear and accessible.

Output format:
What the document says
Explanation
Example (optional)"""

PLAN_PROMPT = """You are a study planner helping the user learn the material in the document.
Use the uploaded documents available through file search. These documents may vary between sessions. Always retrieve relevant passages before giving an answer.
Use the retrieved passages to understand the document's main topics and structure.
Steps:
Identify the main themes or sections of the material.
Break the content into manageable study units.
Create a structured study plan.
Rules:
1) Focus on understanding rather than memorization.
2) Include review and practice.
3) Adapt the plan to the timeframe mentioned by the user.

Output format:
Study Plan
Day 1
Read:
Focus:
Exercise:
Day 2
Read:
Focus:
Exercise:
Continue for the requested duration.
Final Review
Summarize the most important ideas.
Suggest a short self-test."""

QUIZ_PROMPT = """You are a study coach helping the user review the document.
Use the uploaded documents available through file search. These documents may vary between sessions. Always retrieve relevant passages before giving an answer.
Use the retrieved passages to generate quiz questions based only on the document content.
Rules:
1) Questions must be grounded in the retrieved passages. If the retrieved passages do not contain the answer, respond that the information is not present in the uploaded document.
2) Do not ask about material that is not present in the document.
3) Questions should test comprehension rather than trivial details.
4) In a multiple choice part, multiple answers could be correct.
5) Prefer a mix of question types:
- short answer
- conceptual explanation
- key definition
6) Keep the difficulty appropriate for someone learning the material.

If the user is answering a quiz you previously gave, compare the user's answers with the retrieved document passages.
Evaluate correctness and provide feedback.

Output format for creating questions:
Quiz Questions
Instructions to the user: Answer the questions and I will check your responses.

Output format for evaluating answers:
Evaluation
Question 1
User answer:
Assessment: Correct / Partially correct / Incorrect
Explanation:
Repeat for each question.
Finish with a brief summary of the user's understanding and suggestions for improvement."""

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
        async with httpx.AsyncClient(
            base_url=api_base,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            intent = await classify_intent(client, model, history, message)
            upstream = await client.post(
                "/v1/responses",
                json={
                    "model": model,
                    "input": prompt,
                    "instructions": prompt_for_intent(intent),
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
        {"answer": answer, "intent": intent},
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


async def classify_intent(
    client: httpx.AsyncClient,
    model: str,
    history: list[dict[str, str]],
    message: str,
) -> str:
    classifier_input = build_chat_prompt(history, message)

    try:
        response = await client.post(
            "/v1/responses",
            json={
                "model": model,
                "input": classifier_input,
                "instructions": IDENTIFIER_PROMPT,
            },
        )
    except httpx.RequestError:
        return classify_intent_heuristically(history, message)

    payload = parse_json(response)
    label = (extract_response_text(payload) or "").strip().lower()
    if label in INTENT_LABELS:
        return label
    return classify_intent_heuristically(history, message)


def classify_intent_heuristically(
    history: list[dict[str, str]], message: str
) -> str:
    text = f"{' '.join(entry['content'] for entry in history[-4:])} {message}".lower()

    if any(keyword in text for keyword in ["quiz", "questions", "multiple choice"]):
        return "quiz"
    if any(keyword in text for keyword in ["my answers", "check my answers", "evaluate", "assessment:"]):
        return "quiz"
    if any(keyword in text for keyword in ["study plan", "plan", "schedule", "days", "week", "weeks"]):
        return "plan"
    if any(keyword in text for keyword in ["explain", "why", "how does", "what does this mean", "simple terms"]):
        return "explain"
    return "qa"


def prompt_for_intent(intent: str) -> str:
    prompts = {
        "qa": QA_PROMPT,
        "explain": EXPLAIN_PROMPT,
        "plan": PLAN_PROMPT,
        "quiz": QUIZ_PROMPT,
    }
    return prompts.get(intent, QA_PROMPT)


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
