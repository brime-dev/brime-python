"""Synchronous Brime client.

Usage::

    from brime import Brime

    client = Brime(api_key="sk-brime-...")
    result = client.search("BM25 ranking")
"""

from __future__ import annotations

from functools import cached_property
from typing import Any, Literal

import httpx

from brime._http import (
    DEEP_RESEARCH_TIMEOUT_S,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_S,
    build_headers,
    decode_response,
    is_transient_status,
    new_idempotency_key,
    resolve_api_key,
    resolve_base_url,
    retry_delay_seconds,
    sleep_seconds,
    wrap_transport_error,
)
from brime._polling import poll_until_terminal_sync
from brime._response import APIResponse
from brime._streaming import Stream
from brime.errors import BrimeError
from brime.models.extract import ExtractResponse
from brime.models.research import (
    ResearchBasicResponse,
    ResearchDeepInitResponse,
    ResearchSseEvent,
    ResearchStatusResponse,
)
from brime.models.search import SearchResponse


class Brime:
    """Synchronous Brime API client."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._api_key = resolve_api_key(api_key)
        self._base_url = resolve_base_url(base_url)
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def __enter__(self) -> Brime:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ── Raw response observability ─────────────────────────────────────

    @cached_property
    def with_raw_response(self) -> _BrimeRaw:
        """Return a proxy whose methods yield `APIResponse[T]` instead of `T`.

        Use when you need HTTP status, headers, or `request_id` on the
        returned object — e.g. for tracing, retry decisions, or audit logs.
        """
        return _BrimeRaw(self)

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        depth: Literal["instant", "basic", "advanced"] = "basic",
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        time_range: Literal["day", "week", "month", "year"] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_answer: bool | Literal["basic", "advanced"] = True,
        include_images: bool = False,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        timeout: float | None = None,
    ) -> SearchResponse:
        body = _build_search_body(
            query=query,
            depth=depth,
            topic=topic,
            max_results=max_results,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            include_answer=include_answer,
            include_images=include_images,
            domains=domains,
            exclude_domains=exclude_domains,
        )
        data = self._post_json("/v1/search", body, timeout=timeout)
        return SearchResponse.model_validate(data)

    # ── Extract ────────────────────────────────────────────────────────

    def extract(
        self,
        urls: str | list[str],
        *,
        include_metadata: bool = False,
        per_url_timeout_ms: int = 25_000,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> ExtractResponse:
        url_list = [urls] if isinstance(urls, str) else list(urls)
        body: dict[str, Any] = {
            "urls": url_list,
            "include_metadata": include_metadata,
            "per_url_timeout_ms": per_url_timeout_ms,
        }
        idem = idempotency_key or new_idempotency_key()
        data = self._post_json("/v1/extract", body, idempotency_key=idem, timeout=timeout)
        return ExtractResponse.model_validate(data)

    # ── Research ───────────────────────────────────────────────────────

    def research(
        self,
        query: str,
        *,
        depth: Literal["basic", "deep"] = "basic",
        max_rounds: int | None = None,
        fast: bool = False,
        scrape: bool = True,
        query_gen: bool = True,
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        time_range: Literal["day", "week", "month", "year"] | None = None,
        wait: bool = False,
        poll_interval: float = 5.0,
        max_poll_interval: float = 30.0,
        poll_timeout: float = DEEP_RESEARCH_TIMEOUT_S,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> ResearchBasicResponse | ResearchDeepInitResponse | ResearchStatusResponse:
        """Run a research job.

        - depth="basic" → returns ResearchBasicResponse (sync, ~5-30s)
        - depth="deep", wait=False → returns ResearchDeepInitResponse (202)
        - depth="deep", wait=True → polls until terminal, returns
          ResearchStatusResponse

        For depth="deep" an Idempotency-Key is required by the API; the
        SDK auto-generates a UUID4 if one is not provided.
        """
        body = _build_research_body(
            query=query,
            depth=depth,
            max_rounds=max_rounds,
            fast=fast,
            scrape=scrape,
            query_gen=query_gen,
            topic=topic,
            max_results=max_results,
            time_range=time_range,
        )
        idem = idempotency_key
        if depth == "deep" and idem is None:
            idem = new_idempotency_key()
        data = self._post_json("/v1/research", body, idempotency_key=idem, timeout=timeout)

        if depth == "basic":
            return ResearchBasicResponse.model_validate(data)

        init = ResearchDeepInitResponse.model_validate(data)
        if not wait:
            return init
        return poll_until_terminal_sync(
            lambda: self.research_status(init.job_id),
            initial_interval=poll_interval,
            max_interval=max_poll_interval,
            poll_timeout=poll_timeout,
        )

    def research_status(self, job_id: str) -> ResearchStatusResponse:
        data = self._get_json(f"/v1/research/{job_id}")
        return ResearchStatusResponse.model_validate(data)

    def research_stream(
        self,
        query: str,
        *,
        depth: Literal["basic", "deep"] = "deep",
        max_rounds: int | None = None,
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        last_event_id: str | None = None,
        timeout: float | None = None,
    ) -> Stream[ResearchSseEvent]:
        """Stream research events.

        Returns a `Stream[ResearchSseEvent]` which supports `with` syntax
        for guaranteed cleanup. The stream is also a plain iterator — old
        v0.1.x code (`for evt in client.research_stream(...)`) keeps working.

        For `depth="basic"` the request returns SSE directly. For
        `depth="deep"` we initiate the job and connect to its stream URL
        with optional `Last-Event-ID` resume support.
        """
        if depth == "basic":
            return self._open_sse_post(
                "/v1/research",
                body={
                    "query": query,
                    "depth": "basic",
                    "max_rounds": max_rounds or 1,
                    "topic": topic,
                    "max_results": max_results,
                    "stream": True,
                },
                last_event_id=last_event_id,
                timeout=timeout,
            )

        init = self.research(
            query,
            depth="deep",
            max_rounds=max_rounds,
            topic=topic,
            max_results=max_results,
            wait=False,
            timeout=timeout,
        )
        assert isinstance(init, ResearchDeepInitResponse)
        return self._open_sse_get(init.stream_url, last_event_id=last_event_id, timeout=timeout)

    # ── Internal HTTP plumbing ────────────────────────────────────────

    def _post_json(
        self,
        path: str,
        body: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Any:
        res, attempts = self.do_request_with_retry(
            "POST",
            path,
            body=body,
            idempotency_key=idempotency_key,
            timeout=timeout,
            json_body=True,
        )
        return decode_response(res, retries_taken=attempts)

    def _get_json(self, path: str, *, timeout: float | None = None) -> Any:
        res, attempts = self.do_request_with_retry(
            "GET",
            path,
            body=None,
            idempotency_key=None,
            timeout=timeout,
            json_body=False,
        )
        return decode_response(res, retries_taken=attempts)

    def do_request_with_retry(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None,
        idempotency_key: str | None,
        timeout: float | None,
        json_body: bool,
    ) -> tuple[httpx.Response, int]:
        """Issue a non-streaming request with exponential-backoff retry.

        Returns the final `httpx.Response` plus how many retries were
        actually taken (0 on first-attempt success). Idempotency-Key is
        held stable across retries (Stripe pattern) so the gateway
        treats them as the same operation.
        """
        headers = build_headers(
            self._api_key,
            json_body=json_body,
            idempotency_key=idempotency_key,
        )
        last_exc: BrimeError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                res = self._client.request(
                    method,
                    path,
                    headers=headers,
                    json=body if body is not None and json_body else None,
                    timeout=timeout or self._timeout,
                )
            except httpx.HTTPError as exc:
                last_exc = wrap_transport_error(exc, retries_taken=attempt)
                if attempt >= self._max_retries:
                    raise last_exc from exc
                sleep_seconds(retry_delay_seconds(attempt + 1))
                continue
            if (
                res.is_success
                or not is_transient_status(res.status_code)
                or attempt >= self._max_retries
            ):
                return res, attempt
            sleep_seconds(retry_delay_seconds(attempt + 1))
        # Loop body either returns or raises; this is unreachable but keeps
        # the type checker happy about an explicit terminal path.
        assert last_exc is not None
        raise last_exc

    def _open_sse_post(
        self,
        path: str,
        *,
        body: dict[str, Any],
        last_event_id: str | None,
        timeout: float | None,
    ) -> Stream[ResearchSseEvent]:
        extra: dict[str, str] = {}
        if last_event_id:
            extra["last-event-id"] = last_event_id
        headers = build_headers(self._api_key, accept="text/event-stream", extra=extra)
        request = self._client.build_request(
            "POST",
            path,
            json=body,
            headers=headers,
            timeout=timeout or DEEP_RESEARCH_TIMEOUT_S,
        )
        return self._open_stream(request)

    def _open_sse_get(
        self,
        path: str,
        *,
        last_event_id: str | None,
        timeout: float | None,
    ) -> Stream[ResearchSseEvent]:
        extra: dict[str, str] = {}
        if last_event_id:
            extra["last-event-id"] = last_event_id
        headers = build_headers(
            self._api_key, json_body=False, accept="text/event-stream", extra=extra
        )
        request = self._client.build_request(
            "GET",
            path,
            headers=headers,
            timeout=timeout or DEEP_RESEARCH_TIMEOUT_S,
        )
        return self._open_stream(request)

    def _open_stream(self, request: httpx.Request) -> Stream[ResearchSseEvent]:
        try:
            response = self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise wrap_transport_error(exc) from exc
        if not response.is_success:
            try:
                response.read()
                decode_response(response)
            finally:
                response.close()
            # decode_response always raises on non-2xx; the line below is
            # never reached but keeps the type checker happy.
            raise BrimeError(  # pragma: no cover
                "unreachable", status=response.status_code, code="internal_error"
            )
        return Stream(response)


class _BrimeRaw:
    """`with_raw_response` proxy — same method names, `APIResponse[T]` returns.

    Constructed lazily by `Brime.with_raw_response` and re-used by the
    consumer. Holds a reference to the parent client; no extra state.
    """

    def __init__(self, client: Brime) -> None:
        self._client = client

    def search(
        self,
        query: str,
        *,
        depth: Literal["instant", "basic", "advanced"] = "basic",
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        time_range: Literal["day", "week", "month", "year"] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_answer: bool | Literal["basic", "advanced"] = True,
        include_images: bool = False,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[SearchResponse]:
        body = _build_search_body(
            query=query,
            depth=depth,
            topic=topic,
            max_results=max_results,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            include_answer=include_answer,
            include_images=include_images,
            domains=domains,
            exclude_domains=exclude_domains,
        )
        res, attempts = self._client.do_request_with_retry(
            "POST",
            "/v1/search",
            body=body,
            idempotency_key=None,
            timeout=timeout,
            json_body=True,
        )
        data = decode_response(res, retries_taken=attempts)
        return APIResponse(res, data, model_cls=SearchResponse, retries_taken=attempts)

    def extract(
        self,
        urls: str | list[str],
        *,
        include_metadata: bool = False,
        per_url_timeout_ms: int = 25_000,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> APIResponse[ExtractResponse]:
        url_list = [urls] if isinstance(urls, str) else list(urls)
        body: dict[str, Any] = {
            "urls": url_list,
            "include_metadata": include_metadata,
            "per_url_timeout_ms": per_url_timeout_ms,
        }
        idem = idempotency_key or new_idempotency_key()
        res, attempts = self._client.do_request_with_retry(
            "POST",
            "/v1/extract",
            body=body,
            idempotency_key=idem,
            timeout=timeout,
            json_body=True,
        )
        data = decode_response(res, retries_taken=attempts)
        return APIResponse(res, data, model_cls=ExtractResponse, retries_taken=attempts)

    def research_status(self, job_id: str) -> APIResponse[ResearchStatusResponse]:
        res, attempts = self._client.do_request_with_retry(
            "GET",
            f"/v1/research/{job_id}",
            body=None,
            idempotency_key=None,
            timeout=None,
            json_body=False,
        )
        data = decode_response(res, retries_taken=attempts)
        return APIResponse(res, data, model_cls=ResearchStatusResponse, retries_taken=attempts)


def _build_search_body(
    *,
    query: str,
    depth: str,
    topic: str,
    max_results: int,
    time_range: str | None,
    start_date: str | None,
    end_date: str | None,
    include_answer: bool | str,
    include_images: bool,
    domains: list[str] | None,
    exclude_domains: list[str] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": query,
        "depth": depth,
        "topic": topic,
        "max_results": max_results,
        "include_answer": include_answer,
        "include_images": include_images,
    }
    if time_range:
        body["time_range"] = time_range
    if start_date:
        body["start_date"] = start_date
    if end_date:
        body["end_date"] = end_date
    if domains:
        body["domains"] = domains
    if exclude_domains:
        body["exclude_domains"] = exclude_domains
    return body


def _build_research_body(
    *,
    query: str,
    depth: str,
    max_rounds: int | None,
    fast: bool,
    scrape: bool,
    query_gen: bool,
    topic: str,
    max_results: int,
    time_range: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": query,
        "depth": depth,
        "fast": fast,
        "scrape": scrape,
        "query_gen": query_gen,
        "topic": topic,
        "max_results": max_results,
    }
    if max_rounds is not None:
        body["max_rounds"] = max_rounds
    if time_range:
        body["time_range"] = time_range
    return body
