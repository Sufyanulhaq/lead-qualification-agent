import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.extract_rules import extract
from app.main import create_app
from app.mock_crm import MockCrm

HOT_FLOW = ["We need a chatbot connected to our CRM for customer support", "Dana Reyes", "Northwind", "dana@northwind.io", "8000", "asap"]


@pytest.fixture
def parts(tmp_path):
    crm = MockCrm()
    app = create_app(Settings(db_path=str(tmp_path / "leads.db")), extractor=extract, mode="offline", mock_crm=crm)
    return TestClient(app), crm, app


def talk(client, replies):
    sid = client.post("/api/start").json()["session_id"]
    last = None
    for text in replies:
        last = client.post("/api/chat", json={"session_id": sid, "message": text}).json()
    return sid, last


def test_health_reports_the_mode(parts):
    client, _, _ = parts
    assert client.get("/api/health").json() == {"ok": True, "mode": "offline", "crm": "mock demo endpoint"}


def test_full_conversation_saves_scores_and_sends_the_lead(parts):
    client, crm, _ = parts
    sid, last = talk(client, HOT_FLOW)
    assert last["done"] and last["lead"]["label"] == "Hot"
    assert last["lead"]["crm_status"] == "sent" and last["lead"]["crm_attempts"] == 1
    saved = client.get(f"/api/leads/{sid}").json()
    assert saved["email"] == "dana@northwind.io" and saved["crm_status"] == "sent"
    assert saved["services"] == ["automation", "chatbot", "integration"] or "chatbot" in saved["services"]
    assert crm.received[sid]["name"] == "Dana Reyes"


def test_the_card_fills_in_during_the_conversation(parts):
    client, _, _ = parts
    sid = client.post("/api/start").json()["session_id"]
    first = client.post("/api/chat", json={"session_id": sid, "message": "automate our invoices"}).json()
    assert first["done"] is False and first["lead"] is None
    assert first["captured"]["services"] == ["automation", "documents"]


def test_leads_can_be_filtered_by_label(parts):
    client, _, _ = parts
    talk(client, HOT_FLOW)
    talk(client, ["hello", "no", "no", "no", "no", "no", "no", "no", "no", "no", "no", "no"])
    assert len(client.get("/api/leads").json()) == 2
    assert [l["label"] for l in client.get("/api/leads?label=Hot").json()] == ["Hot"]
    assert client.get("/api/leads?label=Lukewarm").status_code == 422


def test_a_crm_outage_still_saves_the_lead(tmp_path):
    crm = MockCrm(fail_first=99)
    app = create_app(Settings(db_path=str(tmp_path / "l.db")), extractor=extract, mode="offline", mock_crm=crm)
    client = TestClient(app)
    sid, last = talk(client, HOT_FLOW)
    assert last["lead"]["crm_status"] == "failed" and last["lead"]["crm_attempts"] == 3
    assert client.get(f"/api/leads/{sid}").json()["crm_status"] == "failed"


def test_unknown_session_is_a_404(parts):
    client, _, _ = parts
    r = client.post("/api/chat", json={"session_id": "nope", "message": "hi"})
    assert r.status_code == 404


@pytest.mark.parametrize("message", ["", "x" * 1001])
def test_message_length_is_validated(parts, message):
    client, _, _ = parts
    sid = client.post("/api/start").json()["session_id"]
    assert client.post("/api/chat", json={"session_id": sid, "message": message}).status_code == 422


def test_whitespace_only_message_is_rejected(parts):
    client, _, _ = parts
    sid = client.post("/api/start").json()["session_id"]
    assert client.post("/api/chat", json={"session_id": sid, "message": "   "}).status_code == 422


def test_a_finished_conversation_does_not_create_a_second_lead(parts):
    client, crm, _ = parts
    sid, _ = talk(client, HOT_FLOW)
    again = client.post("/api/chat", json={"session_id": sid, "message": "one more thing"}).json()
    assert again["lead"] is None
    assert len(client.get("/api/leads").json()) == 1 and len(crm.received) == 1


def test_oldest_session_is_dropped_past_the_cap(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "l.db"), session_cap=2), extractor=extract, mode="offline")
    client = TestClient(app)
    first = client.post("/api/start").json()["session_id"]
    client.post("/api/start"); client.post("/api/start")
    assert client.post("/api/chat", json={"session_id": first, "message": "hi"}).status_code == 404


def test_the_page_is_served(parts):
    client, _, _ = parts
    page = client.get("/")
    assert page.status_code == 200 and "Lead Qualification Agent" in page.text
