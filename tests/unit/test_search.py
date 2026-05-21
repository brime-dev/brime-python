from __future__ import annotations

import httpx
import pytest
import respx

from brime import AuthenticationError, Brime, InvalidRequestError, SearchResponse


@respx.mock
def test_search_happy_path() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "BM25 ranking",
                "answer": "BM25 is a ranking function...",
                "results": [
                    {"title": "BM25 Wiki", "url": "https://en.wikipedia.org/wiki/Okapi_BM25", "content": "...", "score": 0.92}
                ],
                "request_id": "req_test",
                "credits_used": 1,
                "latency_ms": 320,
            },
        )
    )
    client = Brime(api_key="sk-test")
    res = client.search("BM25 ranking")
    assert isinstance(res, SearchResponse)
    assert res.query == "BM25 ranking"
    assert res.answer is not None
    assert len(res.results) == 1
    assert res.results[0].score == 0.92


@respx.mock
def test_search_bad_key_raises_auth_error() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(401, json={"error": {"code": "unauthorized", "message": "bad key"}})
    )
    client = Brime(api_key="sk-bad")
    with pytest.raises(AuthenticationError) as exc:
        client.search("anything")
    assert exc.value.status == 401
    assert exc.value.code == "unauthorized"


@respx.mock
def test_search_400_raises_invalid_request() -> None:
    respx.post("https://api.brime.dev/v1/search").mock(
        return_value=httpx.Response(400, json={"error": {"code": "invalid_request", "message": "query empty"}})
    )
    client = Brime(api_key="sk-test")
    with pytest.raises(InvalidRequestError):
        client.search("")


@respx.mock
def test_search_forwards_optional_filters() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _j
        captured.update(_j.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "query": "x", "answer": None, "results": [],
                "request_id": "r", "credits_used": 0.5, "latency_ms": 5,
            },
        )

    respx.post("https://api.brime.dev/v1/search").mock(side_effect=handler)
    Brime(api_key="sk-test").search(
        "x",
        depth="instant",
        topic="news",
        time_range="week",
        domains=["bbc.com"],
        exclude_domains=["spam.io"],
        max_results=3,
    )
    assert captured["depth"] == "instant"
    assert captured["topic"] == "news"
    assert captured["time_range"] == "week"
    assert captured["domains"] == ["bbc.com"]
    assert captured["exclude_domains"] == ["spam.io"]
    assert captured["max_results"] == 3
