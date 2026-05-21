"""Retry policy + backoff tests for the sync and async clients."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from brime import (
    AsyncBrime,
    Brime,
    RateLimitError,
    TimeoutError,
    UpstreamError,
)
from brime._http import (
    TRANSIENT_STATUS_CODES,
    is_transient_status,
    retry_delay_seconds,
)


def test_transient_status_classification() -> None:
    assert frozenset({500, 502, 503, 504}) == TRANSIENT_STATUS_CODES
    for code in (500, 502, 503, 504):
        assert is_transient_status(code)
    for code in (200, 201, 400, 401, 404, 422, 429):
        assert not is_transient_status(code)


def test_retry_delay_seconds_grows_exponentially() -> None:
    # attempt 1 → ~1s + jitter, attempt 2 → ~2s + jitter, attempt 3 → ~4s + jitter
    # Cap = 8s so attempt 4 stays at ~8s.
    bases = [retry_delay_seconds(n, base=1.0, cap=8.0) for n in range(1, 5)]
    assert 1.0 <= bases[0] <= 1.25
    assert 2.0 <= bases[1] <= 2.25
    assert 4.0 <= bases[2] <= 4.25
    assert 8.0 <= bases[3] <= 8.25


@respx.mock
def test_search_retries_on_503_then_succeeds() -> None:
    route = respx.post("https://api.brime.dev/v1/search").mock(
        side_effect=[
            httpx.Response(503, json={"error": {"code": "upstream_error", "message": "x"}}),
            httpx.Response(
                200,
                json={
                    "query": "q",
                    "answer": None,
                    "results": [],
                    "request_id": "req_test_recovered",
                    "credits_used": 0.5,
                    "latency_ms": 100,
                },
            ),
        ]
    )
    with patch("brime._http.sleep_seconds"):  # don't actually wait
        client = Brime(api_key="sk-brime-test-key-32characters")
        try:
            result = client.search("q")
        finally:
            client.close()
    assert route.call_count == 2
    assert result.request_id == "req_test_recovered"


@respx.mock
def test_search_exhausts_retries_on_persistent_503() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            503,
            json={"error": {"code": "upstream_error", "message": "down"}},
        )
    )
    with patch("brime._http.sleep_seconds"):
        client = Brime(api_key="sk-brime-test-key-32characters", max_retries=2)
        try:
            with pytest.raises(UpstreamError) as exc_info:
                client.search("q")
        finally:
            client.close()
    assert exc_info.value.status == 503
    assert exc_info.value.retries_taken == 2


@respx.mock
def test_search_does_not_retry_on_429_but_surfaces_retry_after() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"code": "rate_limited", "message": "slow down"}},
            headers={"retry-after": "12"},
        )
    )
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        with pytest.raises(RateLimitError) as exc_info:
            client.search("q")
    finally:
        client.close()
    assert exc_info.value.retry_after == 12
    assert exc_info.value.retries_taken == 0


@respx.mock
def test_search_does_not_retry_on_4xx() -> None:
    route = respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            400, json={"error": {"code": "invalid_request", "message": "bad"}}
        )
    )
    client = Brime(api_key="sk-brime-test-key-32characters", max_retries=2)
    try:
        with pytest.raises(Exception):
            client.search("q")
    finally:
        client.close()
    assert route.call_count == 1


@respx.mock
def test_idempotency_key_is_stable_across_retries() -> None:
    seen_keys: list[str] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers.get("idempotency-key", ""))
        if len(seen_keys) == 1:
            return httpx.Response(503, json={"error": {"code": "upstream_error", "message": "x"}})
        return httpx.Response(
            200,
            json={
                "results": [],
                "failed": [],
                "request_id": "req_extract_test",
                "credits_used": 1,
                "latency_ms": 50,
            },
        )

    respx.post("https://api.brime.dev/v1/extract").mock(side_effect=capture)
    with patch("brime._http.sleep_seconds"):
        client = Brime(api_key="sk-brime-test-key-32characters")
        try:
            client.extract(["https://example.com"])
        finally:
            client.close()
    assert len(seen_keys) == 2
    assert seen_keys[0] == seen_keys[1]
    assert seen_keys[0]  # not empty


@respx.mock
def test_timeout_becomes_typed_TimeoutError() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        side_effect=httpx.ConnectTimeout("the request timed out")
    )
    with patch("brime._http.sleep_seconds"):
        client = Brime(api_key="sk-brime-test-key-32characters", max_retries=0)
        try:
            with pytest.raises(TimeoutError) as exc_info:
                client.search("q")
        finally:
            client.close()
    assert exc_info.value.code == "timeout"


# ── Async parity ───────────────────────────────────────────────────────────


@respx.mock
async def test_async_search_retries_on_503() -> None:
    route = respx.post("https://api.brime.dev/v1/search").mock(
        side_effect=[
            httpx.Response(503, json={"error": {"code": "upstream_error", "message": "x"}}),
            httpx.Response(
                200,
                json={
                    "query": "q",
                    "answer": None,
                    "results": [],
                    "request_id": "req_async_recovered",
                    "credits_used": 0.5,
                    "latency_ms": 100,
                },
            ),
        ]
    )

    async def noop(_: float) -> None:
        return None

    import asyncio  # noqa: F401  (kept for any future asyncio.sleep monkeypatch needs)

    with patch("asyncio.sleep", new=noop):
        client = AsyncBrime(api_key="sk-brime-test-key-32characters")
        try:
            result = await client.search("q")
        finally:
            await client.aclose()
    assert route.call_count == 2
    assert result.request_id == "req_async_recovered"
