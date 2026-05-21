"""`with_raw_response` proxy tests — sync + async, observability surface."""

from __future__ import annotations

import httpx
import respx

from brime import APIResponse, AsyncBrime, Brime, SearchResponse


@respx.mock
def test_with_raw_response_search_exposes_status_and_request_id() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            200,
            headers={"x-request-id": "req_test_raw_001", "x-brime-cache": "miss"},
            json={
                "query": "q",
                "answer": "a",
                "results": [{"title": "t", "url": "https://e", "content": "c", "score": 0.9}],
                "request_id": "req_test_raw_001",
                "credits_used": 0.5,
                "latency_ms": 250,
            },
        )
    )
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        raw = client.with_raw_response.search("q")
    finally:
        client.close()

    assert isinstance(raw, APIResponse)
    assert raw.status_code == 200
    assert raw.request_id == "req_test_raw_001"
    assert raw.headers.get("x-brime-cache") == "miss"
    assert raw.retries_taken == 0

    parsed = raw.parse()
    assert isinstance(parsed, SearchResponse)
    assert parsed.request_id == "req_test_raw_001"
    # Second call to parse() should hit the cache (same object).
    assert raw.parse() is parsed


@respx.mock
def test_with_raw_response_is_cached_property() -> None:
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        a = client.with_raw_response
        b = client.with_raw_response
        assert a is b
    finally:
        client.close()


@respx.mock
def test_with_raw_response_extract_propagates_idempotency() -> None:
    captured: dict[str, str] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured["idem"] = request.headers.get("idempotency-key", "")
        return httpx.Response(
            200,
            json={
                "results": [],
                "failed": [],
                "request_id": "req_extract_raw",
                "credits_used": 0,
                "latency_ms": 1,
            },
        )

    respx.post("https://api.brime.dev/v1/extract").mock(side_effect=capture)
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        raw = client.with_raw_response.extract(
            ["https://example.com"],
            idempotency_key="stable-key-2026",
        )
    finally:
        client.close()
    assert captured["idem"] == "stable-key-2026"
    assert raw.status_code == 200


# ── Async parity ───────────────────────────────────────────────────────────


@respx.mock
async def test_async_with_raw_response_search() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            200,
            headers={"x-request-id": "req_async_raw"},
            json={
                "query": "q",
                "answer": "a",
                "results": [],
                "request_id": "req_async_raw",
                "credits_used": 0.5,
                "latency_ms": 100,
            },
        )
    )
    client = AsyncBrime(api_key="sk-brime-test-key-32characters")
    try:
        raw = await client.with_raw_response.search("q")
    finally:
        await client.aclose()
    assert raw.status_code == 200
    assert raw.request_id == "req_async_raw"
    assert raw.parse().request_id == "req_async_raw"
