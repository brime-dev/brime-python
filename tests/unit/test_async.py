from __future__ import annotations

import httpx
import pytest
import respx

from brime import AsyncBrime, AuthenticationError, ResearchBasicResponse, SearchResponse


@respx.mock
async def test_async_search_happy() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "q",
                "answer": "a",
                "results": [],
                "request_id": "r",
                "credits_used": 0.5,
                "latency_ms": 10,
            },
        )
    )
    async with AsyncBrime(api_key="sk-test") as client:
        res = await client.search("q", depth="instant")
    assert isinstance(res, SearchResponse)
    assert res.answer == "a"


@respx.mock
async def test_async_extract_auto_idempotency() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(
            200,
            json={
                "results": [],
                "failed": [],
                "request_id": "r",
                "credits_used": 0,
                "latency_ms": 1,
            },
        )

    respx.post("https://api.brime.dev/v1/extract").mock(side_effect=handler)
    async with AsyncBrime(api_key="sk-test") as client:
        await client.extract(["https://example.com"])
    assert "idempotency-key" in captured


@respx.mock
async def test_async_research_basic() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "q",
                "answer": "a",
                "sources": [],
                "request_id": "r",
                "credits_used": 2,
                "latency_ms": 100,
            },
        )
    )
    async with AsyncBrime(api_key="sk-test") as client:
        res = await client.research("q", depth="basic")
    assert isinstance(res, ResearchBasicResponse)


@respx.mock
async def test_async_error_mapping() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(401, json={"error": {"code": "unauthorized", "message": "bad"}})
    )
    async with AsyncBrime(api_key="sk-bad") as client:
        with pytest.raises(AuthenticationError):
            await client.search("x")
