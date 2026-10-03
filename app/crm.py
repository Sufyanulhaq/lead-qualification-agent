"""Sends a finished lead to a CRM over a webhook. Network calls fail in ordinary ways, so this
retries the failures worth retrying, gives up fast on the ones that will never work, and sends an
Idempotency-Key header so a retry cannot create the lead twice on the other side."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import httpx

RETRY_STATUSES = {408, 429}


@dataclass
class CrmResult:
    status: str  # "sent" or "failed"
    attempts: int
    detail: str


def send_lead(
    client: httpx.Client,
    url: str,
    payload: dict,
    *,
    attempts: int = 3,
    backoff: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> CrmResult:
    headers = {"Idempotency-Key": payload["id"]}
    detail = "no attempt made"
    for attempt in range(1, attempts + 1):
        try:
            response = client.post(url, json=payload, headers=headers)
        except httpx.TransportError as exc:
            detail = f"network error: {type(exc).__name__}"
        else:
            code = response.status_code
            if 200 <= code < 300:
                return CrmResult("sent", attempt, f"accepted with status {code}")
            detail = f"CRM answered {code}"
            if code < 500 and code not in RETRY_STATUSES:
                return CrmResult("failed", attempt, detail + ", not retrying")
        if attempt < attempts:
            sleep(backoff * 2 ** (attempt - 1))
    return CrmResult("failed", attempts, detail + f" after {attempts} attempts")
