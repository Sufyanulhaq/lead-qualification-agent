"""A stand in CRM for the demo and the tests. It behaves like a webhook receiver: it checks the
idempotency key and answers 200 for a repeat instead of storing the lead twice."""
from __future__ import annotations

import json

import httpx


class MockCrm:
    def __init__(self, fail_first: int = 0) -> None:
        self.received: dict[str, dict] = {}
        self.calls = 0
        self.fail_first = fail_first

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.calls <= self.fail_first:
            return httpx.Response(503, json={"error": "try again later"})
        key = request.headers.get("Idempotency-Key")
        if not key:
            return httpx.Response(400, json={"error": "Idempotency-Key header is required"})
        if key in self.received:
            return httpx.Response(200, json={"duplicate": True})
        self.received[key] = json.loads(request.content)
        return httpx.Response(201, json={"created": True})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))
