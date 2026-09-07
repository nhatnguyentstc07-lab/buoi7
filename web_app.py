from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import auth, config, debate, ingest, rag
from core import repository as repo
from core.auth import AuthError
from core.db import init_db
from core.llm import LLMError
from core.repository import ROLE_AI_REBUTTAL, ROLE_USER_ANSWER, ROLE_USER_REBUTTAL

BASE_DIR = Path(__file__).resolve().parent
COOKIE = "learnbuddy_session"
MIN_ANSWER_CHARS = 30

app = FastAPI(title="Learnbuddy AI", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class AuthPayload(BaseModel):
    email: str
    password: str


class RegisterPayload(BaseModel):
    full_name: str
    email: str
    password: str
    confirm: str


class StartPayload(BaseModel):
    chapter_id: int
    difficulty: str = Field(pattern="^(easy|medium|hard)$")


class AnswerPayload(BaseModel):
    session_id: int
    text: str
    choice: str | None = None


def bootstrap() -> None:
    init_db()
    auth.purge_expired_tokens()
    # Only sync lightweight corpus/question-bank files at boot. PDF textbook
    # extraction can be expensive on a small web host, so it is intentionally lazy.
    ingest.sync_corpus()
    ingest.sync_question_banks()
    # Embeddings are intentionally not built on startup. The RAG layer can use
    # lexical retrieval until embeddings are prepared.


try:
    bootstrap()
except Exception as exc:
    # Keep the web server bootable so deployment logs can show the actual issue.
    print(f"[Learnbuddy bootstrap warning] {exc}")


def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE)
    user = auth.user_from_token(token or "")
    if not user:
        raise HTTPException(status_code=401, detail="Bạn chưa đăng nhập.")
    return user


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {"id": user["id"], "full_name": user["full_name"], "email": user["email"]}


def session_payload(session_id: int, user_id: int) -> dict[str, Any]:
    session = repo.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")
    turns = repo.get_turns(session_id)
    verdict = repo.get_verdict(session_id)
    return {"session": session, "turns": turns, "verdict": verdict}


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "api_configured": bool(config.OPENAI_API_KEY)}


@app.post("/api/auth/register")
def register(payload: RegisterPayload, response: Response):
    try:
        user = auth.register(payload.full_name, payload.email, payload.password, payload.confirm)
        token = auth.create_token(user["id"])
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=False, max_age=config.SESSION_TTL_DAYS * 86400)
    return {"user": public_user(user)}


@app.post("/api/auth/login")
def login(payload: AuthPayload, response: Response):
    try:
        user = auth.login(payload.email, payload.password)
        token = auth.create_token(user["id"])
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=False, max_age=config.SESSION_TTL_DAYS * 86400)
    return {"user": public_user(user)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    auth.revoke_token(token or "")
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    return {"user": public_user(current_user(request))}


@app.get("/api/subjects")
def subjects(request: Request):
    current_user(request)
    return {"subjects": repo.list_subjects()}


@app.get("/api/subjects/{subject_id}/chapters")
def chapters(subject_id: int, request: Request):
    current_user(request)
    return {"chapters": repo.list_chapters(subject_id)}


@app.get("/api/stats")
def stats(request: Request):
    user = current_user(request)
    return {"stats": repo.user_stats(user["id"])}


@app.post("/api/sessions")
def start_session(payload: StartPayload, request: Request):
    user = current_user(request)
    chapter = repo.get_chapter(payload.chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
    availability = repo.difficulty_availability(chapter["id"])
    if not chapter["chunk_count"] and not sum(availability.values()):
        raise HTTPException(status_code=400, detail="Chương này chưa có dữ liệu ôn tập.")

    try:
        generated = debate.generate_question(
            chapter,
            payload.difficulty,
            avoid=repo.recent_questions(user["id"], chapter["id"]),
        )
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    session_id = repo.create_session(
        user["id"], chapter["id"], payload.difficulty,
        generated["question"], generated["context"]
    )
    return {
        "session_id": session_id,
        "chapter": chapter,
        "difficulty": payload.difficulty,
        "question": generated["question"],
        "source": generated["source"],
        "mode": generated["mode"],
        "round": 0,
        "stage": "answer",
        "max_rounds": config.MAX_ROUNDS,
        "offline": generated.get("offline", False),
        "turns": [],
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: int, request: Request):
    user = current_user(request)
    return session_payload(session_id, user["id"])


@app.post("/api/sessions/answer")
def answer(payload: AnswerPayload, request: Request):
    user = current_user(request)
    session = repo.get_session(payload.session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")
    if session["status"] == "done":
        raise HTTPException(status_code=400, detail="Phiên này đã kết thúc.")

    text = payload.text.strip()
    if len(text) < MIN_ANSWER_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Hãy trình bày dài hơn (tối thiểu {MIN_ANSWER_CHARS} ký tự)."
        )

    question = session["question"]
    _, choices = debate.parse_choices(question)
    content = text
    if choices and payload.choice:
        content = f"**Đáp án chọn: {payload.choice}**\n\n{text}"
    elif choices and not payload.choice:
        raise HTTPException(status_code=400, detail="Hãy chọn một đáp án trước khi gửi.")

    turns = repo.get_turns(payload.session_id)
    user_role = ROLE_USER_ANSWER if not turns else ROLE_USER_REBUTTAL
    current_round = max([int(t["round_no"]) for t in turns], default=0)
    # The first student answer is round 0; subsequent student replies use the
    # current AI round number.
    repo.add_turn(payload.session_id, current_round, user_role, content)

    next_round = current_round + 1
    chapter = repo.get_chapter(session["chapter_id"])
    if not chapter:
        raise HTTPException(status_code=500, detail="Dữ liệu chương không còn tồn tại.")

    if next_round <= config.MAX_ROUNDS:
        try:
            result = debate.generate_rebuttal(
                chapter, session["difficulty"], question,
                repo.get_turns(payload.session_id), next_round
            )
        except LLMError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        repo.add_turn(payload.session_id, next_round, ROLE_AI_REBUTTAL, result["content"])
        return {
            "stage": "rebut",
            "round": next_round,
            "max_rounds": config.MAX_ROUNDS,
            "rebuttal": result["content"],
            "offline": result.get("offline", False),
            "turns": repo.get_turns(payload.session_id),
        }

    try:
        verdict = debate.judge(
            chapter, session["difficulty"], question,
            repo.get_turns(payload.session_id)
        )
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    repo.save_verdict(payload.session_id, verdict)
    repo.close_session(payload.session_id)
    return {
        "stage": "done",
        "round": current_round,
        "max_rounds": config.MAX_ROUNDS,
        "verdict": verdict,
        "turns": repo.get_turns(payload.session_id),
    }


@app.post("/api/sessions/finish")
def finish(payload: dict, request: Request):
    user = current_user(request)
    session_id = int(payload.get("session_id", 0))
    session = repo.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")
    turns = repo.get_turns(session_id)
    if not turns:
        raise HTTPException(status_code=400, detail="Bạn cần trả lời ít nhất một lượt trước khi chấm.")
    if session["status"] != "done":
        chapter = repo.get_chapter(session["chapter_id"])
        try:
            verdict = debate.judge(chapter, session["difficulty"], session["question"], turns)
        except LLMError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        repo.save_verdict(session_id, verdict)
        repo.close_session(session_id)
    return session_payload(session_id, user["id"])


@app.get("/api/history")
def history(request: Request):
    user = current_user(request)
    return {"items": repo.history(user["id"], 50)}


@app.get("/api/history/{session_id}")
def history_detail(session_id: int, request: Request):
    user = current_user(request)
    return session_payload(session_id, user["id"])
