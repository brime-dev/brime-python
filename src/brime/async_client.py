"""Asynchronous Brime client (mirror of brime.client.Brime)."""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Union

import httpx

from brime._http import (
    DEEP_RESEARCH_TIMEOUT_S,
    DEFAULT_TIMEOUT_S,
    build_headers,
    decode_response,
    new_idempotency_key,
    resolve_api_key,
    resolve_base_url,
    wrap_transport_error,
)
from brime._polling import poll_until_terminal_async
from brime._sse import iter_sse_async
from brime.errors import BrimeError
from brime.models.extract import ExtractResponse
from brime.models.research import (
    ResearchBasicResponse,
    ResearchDeepInitResponse,
    ResearchSseEvent,
    ResearchStatusResponse,
)
from brime.models.search import SearchResponse


class AsyncBrime:
    """Asynchronous Brime API client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._api_key = resolve_api_key(api_key)
        self._base_url = resolve_base_url(base_url)
        self._timeout = timeout
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def __aenter__(self) -> "AsyncBrime":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── Search ─────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        depth: Literal["instant", "basic", "advanced"] = "basic",
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        time_range: Optional[Literal["day", "week", "month", "year"]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_answer: Union[bool, Literal["basic", "advanced"]] = True,
        include_images: bool = False,
        domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> SearchResponse:
        body: Dict[str, Any] = {
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
        data = await self._post_json("/v1/search", body, timeout=timeout)
        return SearchResponse.model_validate(data)

    # ── Extract ────────────────────────────────────────────────────────

    async def extract(
        self,
        urls: Union[str, List[str]],
        *,
        include_metadata: bool = False,
        per_url_timeout_ms: int = 25_000,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ExtractResponse:
        url_list = [urls] if isinstance(urls, str) else list(urls)
        body: Dict[str, Any] = {
            "urls": url_list,
            "include_metadata": include_metadata,
            "per_url_timeout_ms": per_url_timeout_ms,
        }
        idem = idempotency_key or new_idempotency_key()
        data = await self._post_json(
            "/v1/extract", body, idempotency_key=idem, timeout=timeout
        )
        return ExtractResponse.model_validate(data)

    # ── Research ───────────────────────────────────────────────────────

    async def research(
        self,
        query: str,
        *,
        depth: Literal["basic", "deep"] = "basic",
        max_rounds: Optional[int] = None,
        fast: bool = False,
        scrape: bool = True,
        query_gen: bool = True,
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        time_range: Optional[Literal["day", "week", "month", "year"]] = None,
        wait: bool = False,
        poll_interval: float = 5.0,
        max_poll_interval: float = 30.0,
        poll_timeout: float = DEEP_RESEARCH_TIMEOUT_S,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Union[ResearchBasicResponse, ResearchDeepInitResponse, ResearchStatusResponse]:
        body: Dict[str, Any] = {
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

        idem = idempotency_key
        if depth == "deep" and idem is None:
            idem = new_idempotency_key()
        data = await self._post_json(
            "/v1/research", body, idempotency_key=idem, timeout=timeout
        )
        if depth == "basic":
            return ResearchBasicResponse.model_validate(data)
        init = ResearchDeepInitResponse.model_validate(data)
        if not wait:
            return init

        async def fetch() -> ResearchStatusResponse:
            return await self.research_status(init.job_id)

        return await poll_until_terminal_async(
            fetch,
            initial_interval=poll_interval,
            max_interval=max_poll_interval,
            poll_timeout=poll_timeout,
        )

    async def research_status(self, job_id: str) -> ResearchStatusResponse:
        data = await self._get_json(f"/v1/research/{job_id}")
        return ResearchStatusResponse.model_validate(data)

    async def research_stream(
        self,
        query: str,
        *,
        depth: Literal["basic", "deep"] = "deep",
        max_rounds: Optional[int] = None,
        topic: Literal["general", "news", "finance"] = "general",
        max_results: int = 5,
        last_event_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[ResearchSseEvent]:
        if depth == "basic":
            async for evt in self._sse_post(
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
            ):
                yield evt
            return
        init = await self.research(
            query,
            depth="deep",
            max_rounds=max_rounds,
            topic=topic,
            max_results=max_results,
            wait=False,
            timeout=timeout,
        )
        assert isinstance(init, ResearchDeepInitResponse)
        async for evt in self._sse_get(
            init.stream_url, last_event_id=last_event_id, timeout=timeout
        ):
            yield evt

    # ── Internal HTTP plumbing ────────────────────────────────────────

    async def _post_json(
        self,
        path: str,
        body: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        headers = build_headers(self._api_key, idempotency_key=idempotency_key)
        try:
            res = await self._client.post(
                path, json=body, headers=headers, timeout=timeout or self._timeout
            )
        except httpx.HTTPError as exc:
            raise wrap_transport_error(exc) from exc
        return decode_response(res)

    async def _get_json(self, path: str, *, timeout: Optional[float] = None) -> Any:
        headers = build_headers(self._api_key, json_body=False)
        try:
            res = await self._client.get(
                path, headers=headers, timeout=timeout or self._timeout
            )
        except httpx.HTTPError as exc:
            raise wrap_transport_error(exc) from exc
        return decode_response(res)

    async def _sse_post(
        self,
        path: str,
        *,
        body: Dict[str, Any],
        last_event_id: Optional[str],
        timeout: Optional[float],
    ) -> AsyncIterator[ResearchSseEvent]:
        extra: Dict[str, str] = {}
        if last_event_id:
            extra["last-event-id"] = last_event_id
        headers = build_headers(self._api_key, accept="text/event-stream", extra=extra)
        try:
            async with self._client.stream(
                "POST",
                path,
                json=body,
                headers=headers,
                timeout=timeout or DEEP_RESEARCH_TIMEOUT_S,
            ) as res:
                if not res.is_success:
                    await res.aread()
                    decode_response(res)
                async for evt in iter_sse_async(res.aiter_bytes()):
                    yield ResearchSseEvent.model_validate(evt)
        except httpx.HTTPError as exc:
            if isinstance(exc, BrimeError):  # pragma: no cover
                raise
            raise wrap_transport_error(exc) from exc

    async def _sse_get(
        self,
        path: str,
        *,
        last_event_id: Optional[str],
        timeout: Optional[float],
    ) -> AsyncIterator[ResearchSseEvent]:
        extra: Dict[str, str] = {}
        if last_event_id:
            extra["last-event-id"] = last_event_id
        headers = build_headers(
            self._api_key, json_body=False, accept="text/event-stream", extra=extra
        )
        try:
            async with self._client.stream(
                "GET",
                path,
                headers=headers,
                timeout=timeout or DEEP_RESEARCH_TIMEOUT_S,
            ) as res:
                if not res.is_success:
                    await res.aread()
                    decode_response(res)
                async for evt in iter_sse_async(res.aiter_bytes()):
                    yield ResearchSseEvent.model_validate(evt)
        except httpx.HTTPError as exc:
            if isinstance(exc, BrimeError):  # pragma: no cover
                raise
            raise wrap_transport_error(exc) from exc
