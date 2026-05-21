from __future__ import annotations

import httpx
import respx

from brime import Brime, ExtractMetadata, ExtractResponse


@respx.mock
def test_extract_auto_idempotency_key() -> None:
    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com",
                        "markdown": "# Hi",
                        "method": "worker_static",
                        "content_type": "html",
                    }
                ],
                "failed": [],
                "request_id": "r",
                "credits_used": 1,
                "latency_ms": 100,
            },
        )

    respx.post("https://api.brime.dev/v1/extract").mock(side_effect=handler)
    res = Brime(api_key="sk-test").extract("https://example.com")
    assert isinstance(res, ExtractResponse)
    assert "idempotency-key" in captured_headers
    assert len(captured_headers["idempotency-key"]) == 36  # uuid4
    assert len(res.results) == 1


@respx.mock
def test_extract_user_idempotency_key_passthrough() -> None:
    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
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
    Brime(api_key="sk-test").extract(["https://a"], idempotency_key="user-supplied-key")
    assert captured_headers["idempotency-key"] == "user-supplied-key"


@respx.mock
def test_extract_typed_metadata() -> None:
    """Server emits unified metadata block; SDK exposes it as ExtractMetadata."""
    respx.post("https://api.brime.dev/v1/extract").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com",
                        "markdown": "# hi",
                        "method": "worker_static",
                        "content_type": "html",
                        "status": 200,
                        "metadata": {
                            "title": "Example Domain",
                            "description": "Illustrative example.",
                            "author": "IANA",
                            "published_date": "2024-01-15T00:00:00Z",
                            "canonical": "https://example.com/",
                            "og_image": "https://example.com/og.png",
                            "language": "en",
                        },
                    }
                ],
                "failed": [],
                "request_id": "r",
                "credits_used": 1,
                "latency_ms": 50,
            },
        )
    )
    res = Brime(api_key="sk-test").extract(["https://example.com"])
    item = res.results[0]
    assert isinstance(item.metadata, ExtractMetadata)
    assert item.metadata.title == "Example Domain"
    assert item.metadata.description == "Illustrative example."
    assert item.metadata.author == "IANA"
    assert item.metadata.published_date == "2024-01-15T00:00:00Z"
    assert item.metadata.canonical == "https://example.com/"
    assert item.metadata.og_image == "https://example.com/og.png"
    assert item.metadata.language == "en"


@respx.mock
def test_extract_metadata_optional_when_absent() -> None:
    """No metadata on the wire → field is None, not a default object."""
    respx.post("https://api.brime.dev/v1/extract").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com",
                        "markdown": "body",
                        "method": "worker_static",
                        "content_type": "html",
                    }
                ],
                "failed": [],
                "request_id": "r",
                "credits_used": 1,
                "latency_ms": 10,
            },
        )
    )
    res = Brime(api_key="sk-test").extract(["https://example.com"])
    assert res.results[0].metadata is None


@respx.mock
def test_extract_failed_array() -> None:
    respx.post("https://api.brime.dev/v1/extract").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [],
                "failed": [
                    {
                        "url": "https://bad",
                        "error": {"code": "fetch_failed", "message": "404", "needs_browser": False},
                    }
                ],
                "request_id": "r",
                "credits_used": 0,
                "latency_ms": 50,
            },
        )
    )
    res = Brime(api_key="sk-test").extract(["https://bad"])
    assert len(res.failed) == 1
    assert res.failed[0].error.code == "fetch_failed"
