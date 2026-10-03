"""The web API. Start it with: uvicorn app.main:create_app --factory"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .conversation import GREETING, Session, handle_message
from .crm import send_lead
from .extract_rules import extract as rules_extract
from .mock_crm import MockCrm
from .store import LeadStore

STATIC = Path(__file__).resolve().parent.parent / "static"


class ChatIn(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=1000)


def build_extractor(settings: Settings):
    """Claude when an API key is set, plain rules otherwise."""
    if not settings.anthropic_api_key:
        return rules_extract, "offline"
    import anthropic

    from .extract_llm import ClaudeExtractor

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return ClaudeExtractor(client, settings.model), "claude"


def create_app(settings: Settings | None = None, extractor=None, mode: str | None = None, crm_client=None, mock_crm: MockCrm | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if extractor is None:
        extractor, detected = build_extractor(settings)
        mode = mode or detected
    mode = mode or "custom"

    store = LeadStore(settings.db_path)
    if settings.crm_webhook_url:
        crm_url = settings.crm_webhook_url
        crm_target = urlparse(crm_url).netloc
        crm_http = crm_client or httpx.Client(timeout=5)
    else:
        mock_crm = mock_crm or MockCrm()
        crm_url, crm_target = "http://mock-crm.local/leads", "mock demo endpoint"
        crm_http = mock_crm.client()

    sessions: dict[str, Session] = {}
    lock = threading.Lock()
    app = FastAPI(title="Lead Qualification Agent")
    app.state.store = store
    app.state.mock_crm = mock_crm

    @app.get("/api/health")
    def health():
        return {"ok": True, "mode": mode, "crm": crm_target}

    @app.post("/api/start")
    def start():
        with lock:
            while len(sessions) >= settings.session_cap:
                sessions.pop(next(iter(sessions)))
            session = Session()
            sessions[session.id] = session
        return {"session_id": session.id, "reply": GREETING, "mode": mode}

    @app.post("/api/chat")
    def chat(body: ChatIn):
        message = body.message.strip()
        if not message:
            raise HTTPException(422, "message is empty")
        with lock:
            session = sessions.get(body.session_id)
            if session is None:
                raise HTTPException(404, "unknown session, call /api/start first")
            was_done = session.done
            reply, score = handle_message(session, message, extractor)
            captured = dict(session.fields)
        result = {"reply": reply, "done": session.done, "captured": captured, "lead": None}
        if score is not None and not was_done:
            lead = {
                "id": session.id,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "name": captured.get("name"),
                "company": captured.get("company"),
                "email": captured.get("email"),
                "need": captured.get("need"),
                "services": captured.get("services", []),
                "budget_amount": captured.get("budget_amount"),
                "timeline_months": captured.get("timeline_months"),
                "score": score.total,
                "label": score.label,
                "reasons": score.reasons,
            }
            store.save(lead)
            outcome = send_lead(crm_http, crm_url, lead)
            store.set_crm(lead["id"], outcome.status, outcome.attempts)
            lead.update(crm_status=outcome.status, crm_attempts=outcome.attempts, crm_detail=outcome.detail, crm_target=crm_target)
            result["lead"] = lead
        return result

    @app.get("/api/leads")
    def leads(label: str | None = None):
        if label and label not in ("Hot", "Warm", "Cold"):
            raise HTTPException(422, "label must be Hot, Warm or Cold")
        return store.list(label)

    @app.get("/api/leads/{lead_id}")
    def lead(lead_id: str):
        found = store.get(lead_id)
        if not found:
            raise HTTPException(404, "no such lead")
        return found

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app

