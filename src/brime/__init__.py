"""Brime — Official Python SDK."""

from brime._response import APIResponse, AsyncAPIResponse
from brime._streaming import AsyncStream, Stream
from brime._version import __version__
from brime.client import Brime
from brime.errors import (
    AuthenticationError,
    BrimeError,
    ConnectionError,
    InsufficientCreditsError,
    InternalError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    UpstreamError,
)
from brime.models.extract import (
    ExtractFailedItem,
    ExtractMetadata,
    ExtractResponse,
    ExtractResultItem,
)
from brime.models.research import (
    ResearchBasicResponse,
    ResearchDeepInitResponse,
    ResearchSseEvent,
    ResearchStatusResponse,
)
from brime.models.search import SearchResponse, SearchResultItem

__all__ = [
    "APIResponse",
    "AsyncAPIResponse",
    "AsyncStream",
    "AuthenticationError",
    "Brime",
    "BrimeError",
    "ConnectionError",
    "ExtractFailedItem",
    "ExtractMetadata",
    "ExtractResponse",
    "ExtractResultItem",
    "InsufficientCreditsError",
    "InternalError",
    "InvalidRequestError",
    "NotFoundError",
    "RateLimitError",
    "ResearchBasicResponse",
    "ResearchDeepInitResponse",
    "ResearchSseEvent",
    "ResearchStatusResponse",
    "SearchResponse",
    "SearchResultItem",
    "Stream",
    "TimeoutError",
    "UpstreamError",
    "__version__",
]


def __getattr__(name: str) -> object:  # pragma: no cover
    """Lazy AsyncBrime import (added in S6)."""
    if name == "AsyncBrime":
        from brime.async_client import AsyncBrime

        return AsyncBrime
    raise AttributeError(name)
