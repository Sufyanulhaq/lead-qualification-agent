import httpx

from app.crm import send_lead
from app.mock_crm import MockCrm

PAYLOAD = {"id": "abc123", "label": "Hot", "score": 88}


def no_sleep(_):
    pass


def test_sends_once_with_an_idempotency_key():
    crm = MockCrm()
    result = send_lead(crm.client(), "http://x/leads", PAYLOAD, sleep=no_sleep)
    assert (result.status, result.attempts) == ("sent", 1)
    assert crm.received["abc123"]["score"] == 88


def test_retries_a_server_error_and_then_succeeds():
    crm = MockCrm(fail_first=2)
    waits = []
    result = send_lead(crm.client(), "http://x/leads", PAYLOAD, sleep=waits.append)
    assert (result.status, result.attempts) == ("sent", 3)
    assert waits == [0.5, 1.0]  # backoff doubles


def test_gives_up_after_the_attempt_limit():
    crm = MockCrm(fail_first=99)
    result = send_lead(crm.client(), "http://x/leads", PAYLOAD, attempts=3, sleep=no_sleep)
    assert result.status == "failed" and result.attempts == 3 and crm.calls == 3
    assert "503" in result.detail


def test_does_not_retry_a_client_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    result = send_lead(client, "http://x/leads", PAYLOAD, sleep=no_sleep)
    assert (result.status, result.attempts) == ("failed", 1)
    assert "not retrying" in result.detail


def test_retries_a_rate_limit():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429 if len(calls) == 1 else 200)

    result = send_lead(httpx.Client(transport=httpx.MockTransport(handler)), "http://x/leads", PAYLOAD, sleep=no_sleep)
    assert (result.status, result.attempts) == ("sent", 2)


def test_retries_network_errors():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("refused")
        return httpx.Response(200)

    result = send_lead(httpx.Client(transport=httpx.MockTransport(handler)), "http://x/leads", PAYLOAD, sleep=no_sleep)
    assert (result.status, result.attempts) == ("sent", 3)


def test_a_repeated_send_does_not_create_a_second_lead():
    crm = MockCrm()
    client = crm.client()
    send_lead(client, "http://x/leads", PAYLOAD, sleep=no_sleep)
    again = send_lead(client, "http://x/leads", PAYLOAD, sleep=no_sleep)
    assert again.status == "sent" and len(crm.received) == 1
