"""Server-Sent Events parser.

Brime /v1/research stream emits frames like::

    event: tool_call\\n
    data: {"round": 1, "queries": ["..."]}\\n
    \\n

This module turns httpx byte iterators into ResearchSseEvent dicts.
Handles fragmented chunks (a single SSE frame may arrive across multiple
read() calls) and the [DONE] terminator.
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Dict, Iterator, List, Optional


class _SseAccumulator:
    """Stateful frame buffer.

    Feed `feed(text)` repeatedly with raw decoded chunks. After each feed,
    drain `pop_frames()` to collect complete SSE frames. A frame is delimited
    by a blank line (\\n\\n).
    """

    __slots__ = ("_buf", "_done")

    def __init__(self) -> None:
        self._buf = ""
        self._done = False

    @property
    def done(self) -> bool:
        return self._done

    def feed(self, chunk: str) -> None:
        self._buf += chunk

    def pop_frames(self) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        while True:
            idx = self._buf.find("\n\n")
            if idx < 0:
                break
            frame = self._buf[:idx]
            self._buf = self._buf[idx + 2 :]
            evt = _parse_frame(frame)
            if evt is None:
                continue
            if evt is _DONE_SENTINEL:
                self._done = True
                break
            out.append(evt)
        return out


_DONE_SENTINEL: Dict[str, object] = {"__done__": True}


def _parse_frame(frame: str) -> Optional[Dict[str, object]]:
    """Convert a raw SSE frame text into a normalized event dict.

    Returns None for empty/comment-only frames; returns _DONE_SENTINEL on
    `data: [DONE]` lines (used by some adapters).
    """
    event_type: Optional[str] = None
    event_id: Optional[str] = None
    data_lines: List[str] = []
    for raw_line in frame.split("\n"):
        line = raw_line.rstrip("\r")
        if not line or line.startswith(":"):
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")
        else:
            field, value = line, ""
        if field == "event":
            event_type = value
        elif field == "id":
            event_id = value
        elif field == "data":
            data_lines.append(value)

    if not data_lines and event_type is None:
        return None

    raw_data = "\n".join(data_lines)
    if raw_data.strip() == "[DONE]":
        return _DONE_SENTINEL

    parsed: object
    if raw_data == "":
        parsed = {}
    else:
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed = raw_data  # fall back to raw string payload

    return {
        "event": event_type or "message",
        "data": parsed,
        "id": event_id,
    }


def iter_sse_sync(byte_iter: Iterator[bytes]) -> Iterator[Dict[str, object]]:
    acc = _SseAccumulator()
    for chunk in byte_iter:
        if not chunk:
            continue
        acc.feed(chunk.decode("utf-8", errors="replace"))
        for evt in acc.pop_frames():
            yield evt
        if acc.done:
            return


async def iter_sse_async(byte_iter: AsyncIterator[bytes]) -> AsyncIterator[Dict[str, object]]:
    acc = _SseAccumulator()
    async for chunk in byte_iter:
        if not chunk:
            continue
        acc.feed(chunk.decode("utf-8", errors="replace"))
        for evt in acc.pop_frames():
            yield evt
        if acc.done:
            return
