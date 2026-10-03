"""SQLite storage for finished leads. One lead per conversation, saving twice updates the same row."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

COLUMNS = (
    "id", "created_at", "name", "company", "email", "need", "services", "budget_amount",
    "timeline_months", "score", "label", "reasons", "crm_status", "crm_attempts",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    name TEXT, company TEXT, email TEXT, need TEXT,
    services TEXT NOT NULL DEFAULT '[]',
    budget_amount REAL, timeline_months REAL,
    score INTEGER NOT NULL, label TEXT NOT NULL,
    reasons TEXT NOT NULL DEFAULT '[]',
    crm_status TEXT NOT NULL DEFAULT 'pending',
    crm_attempts INTEGER NOT NULL DEFAULT 0
)
"""


class LeadStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute(SCHEMA)
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        lead = dict(row)
        lead["services"] = json.loads(lead["services"])
        lead["reasons"] = json.loads(lead["reasons"])
        return lead

    def save(self, lead: dict) -> None:
        values = {c: lead.get(c) for c in COLUMNS}
        values["services"] = json.dumps(lead.get("services", []))
        values["reasons"] = json.dumps(lead.get("reasons", []))
        values["crm_status"] = lead.get("crm_status", "pending")
        values["crm_attempts"] = lead.get("crm_attempts", 0)
        names = ", ".join(COLUMNS)
        marks = ", ".join(f":{c}" for c in COLUMNS)
        updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "id")
        with closing(self._connect()) as db:
            db.execute(f"INSERT INTO leads ({names}) VALUES ({marks}) ON CONFLICT(id) DO UPDATE SET {updates}", values)
            db.commit()

    def set_crm(self, lead_id: str, status: str, attempts: int) -> None:
        with closing(self._connect()) as db:
            db.execute("UPDATE leads SET crm_status=?, crm_attempts=? WHERE id=?", (status, attempts, lead_id))
            db.commit()

    def get(self, lead_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, label: str | None = None, limit: int = 100) -> list[dict]:
        sql, args = "SELECT * FROM leads", []
        if label:
            sql += " WHERE label=?"
            args.append(label)
        sql += " ORDER BY created_at DESC, id LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as db:
            return [self._row(r) for r in db.execute(sql, args).fetchall()]
