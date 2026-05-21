"""Research deep-mode polling helpers.

`research(depth="deep", wait=True)` blocks until the job reaches a
terminal state (complete | errored | timeout) or `poll_timeout` elapses.

Design:
    - Caller passes a status fetcher (sync or async closure)
    - We delay between polls with optional jitter-free exponential backoff
      capped at `max_interval`
    - Terminal states stop polling; on poll_timeout we raise TimeoutError
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from typing import Callable

from brime.models.research import ResearchStatusResponse

TERMINAL = ("complete", "errored", "timeout")


def _next_interval(prev: float, max_interval: float) -> float:
    return min(prev * 1.5, max_interval)


def poll_until_terminal_sync(
    fetch: Callable[[], ResearchStatusResponse],
    *,
    initial_interval: float,
    max_interval: float,
    poll_timeout: float,
) -> ResearchStatusResponse:
    deadline = time.monotonic() + poll_timeout
    interval = initial_interval
    while True:
        status = fetch()
        if status.status in TERMINAL:
            return status
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"research polling exceeded {poll_timeout}s "
                f"(last status: {status.status}, round {status.current_round}/{status.max_rounds})"
            )
        time.sleep(min(interval, remaining))
        interval = _next_interval(interval, max_interval)


async def poll_until_terminal_async(
    fetch: Callable[[], Awaitable[ResearchStatusResponse]],
    *,
    initial_interval: float,
    max_interval: float,
    poll_timeout: float,
) -> ResearchStatusResponse:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + poll_timeout
    interval = initial_interval
    while True:
        status = await fetch()
        if status.status in TERMINAL:
            return status
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(
                f"research polling exceeded {poll_timeout}s "
                f"(last status: {status.status}, round {status.current_round}/{status.max_rounds})"
            )
        await asyncio.sleep(min(interval, remaining))
        interval = _next_interval(interval, max_interval)
