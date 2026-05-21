"""Brime — Official Python SDK."""

from brime._version import __version__
from brime.client import Brime
from brime.errors import (
    AuthenticationError,
    BrimeError,
    InsufficientCreditsError,
    InternalError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
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
    "__version__",
    "Brime",
    "BrimeError",
    "AuthenticationError",
    "RateLimitError",
    "InsufficientCreditsError",
    "InvalidRequestError",
    "NotFoundError",
    "UpstreamError",
    "InternalError",
    "SearchResponse",
    "SearchResultItem",
    "ExtractResponse",
    "ExtractResultItem",
    "ExtractFailedItem",
    "ExtractMetadata",
    "ResearchBasicResponse",
    "ResearchDeepInitResponse",
    "ResearchStatusResponse",
    "ResearchSseEvent",
]


def __getattr__(name: str) -> object:  # pragma: no cover
    """Lazy AsyncBrime import (added in S6)."""
    if name == "AsyncBrime":
        from brime.async_client import AsyncBrime
        return AsyncBrime
    raise AttributeError(name)
