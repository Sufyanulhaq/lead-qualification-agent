"""Settings read from environment variables. Everything has a default so the demo starts with none."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = None
    model: str = "claude-haiku-4-5"
    db_path: str = "data/leads.db"
    crm_webhook_url: str | None = None
    session_cap: int = 1000

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            model=os.environ.get("LEAD_MODEL", cls.model),
            db_path=os.environ.get("LEAD_DB", cls.db_path),
            crm_webhook_url=os.environ.get("CRM_WEBHOOK_URL") or None,
            session_cap=int(os.environ.get("SESSION_CAP", cls.session_cap)),
        )
