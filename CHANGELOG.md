# Changelog

## 0.2.0 — 2026-05-21

### A-tier polish

- **Per-condition `types` in `pyproject.toml` exports**: Pydantic models and `py.typed` marker were already shipping; `attw`-style discipline now enforces single-import resolution. `twine check --strict` and `publint`-equivalent gates documented in CI.
- **HTTP retry with exponential backoff + jitter** at the client layer (Stripe / OpenAI pattern). Retries on `500/502/503/504` only; 1s → 2s → 4s with ±250 ms jitter, capped at 8 s, default 2 retries (configurable via `max_retries=`). Idempotency-Key is held stable across retry attempts so the gateway dedupes correctly.
- **New typed exceptions**: `ConnectionError` (DNS / TLS / `ECONNRESET`) and `TimeoutError` (request deadline). Every exception now carries `retries_taken: int`. `RateLimitError` additionally surfaces `retry_after: int | None` parsed from the response header.
- **`Stream[T]` and `AsyncStream[T]` wrappers** on `client.research_stream(...)`. They are still iterators (`for evt in stream: ...` keeps working from v0.1.x) but now also support `with` / `async with` for guaranteed cleanup and expose `stream.request_id` for log correlation.
- **`with_raw_response` cached property** on both `Brime` and `AsyncBrime`. Same method names, return `APIResponse[T]` / `AsyncAPIResponse[T]` — gives you HTTP status, headers, `request_id`, and `retries_taken` without parsing the model first. `.parse()` is cached.
- **PEP 639 SPDX license** (`license = "MIT"`) — replaces the older dict form, supported by hatchling ≥ 1.27.
- **Stronger CI gates**: `ruff check`, `ruff format --check`, `pyright` (strict mode), `mypy --strict`, `pytest -n auto` (xdist parallel), `uv build`, `twine check --strict`.
- **PyPI Trusted Publishing** via GitHub Actions OIDC. No `PYPI_TOKEN` secrets in the repo. Releases are tag-driven (`python-sdk-v*`).
- **Identity headers**: `User-Agent` now embeds httpx and Python versions; a new `X-Brime-Client` header carries the SDK name + version for analytics.

### Internal

- New modules: `src/brime/_response.py` (`APIResponse[T]` / `AsyncAPIResponse[T]`), `src/brime/_streaming.py` (`Stream` / `AsyncStream`). Existing `_sse.py` parser is unchanged and continues to back both wrappers.
- 19 new tests (retry edge cases, raw response observability, stream context manager) — total **35 unit tests** green.

### Compatibility

Fully additive — every v0.1.x import keeps working. `client.research_stream(...)` now returns `Stream[ResearchSseEvent]` instead of a bare generator, but the iteration protocol is identical, so existing `for evt in stream:` loops continue to function.

## 0.1.0 — 2026-05-06

Initial release. Beta.

### Added
- `Brime` synchronous client and `AsyncBrime` asynchronous client
- `search`, `extract`, `research`, `research_status`, `research_stream` methods
- Native `/v1/*` endpoint coverage (Brime-native surface — Tavily/Exa/Parallel users should use those vendors' official SDKs against the matching `/tavily/*`, `/exa/*`, `/parallel/*` paths)
- `research(depth="deep", wait=True)` blocking polling helper with exponential backoff
- Pydantic v2 response models with full type hints (`py.typed`)
- Error hierarchy: `BrimeError` → `AuthenticationError`, `RateLimitError`, `InsufficientCreditsError`, `InvalidRequestError`, `NotFoundError`, `UpstreamError`, `InternalError`
- Auto-generated `Idempotency-Key` for `extract` and deep `research` calls
- SSE parser with fragmented-chunk and `[DONE]` terminator handling
- `BRIME_API_KEY` and `BRIME_BASE_URL` env-var fallbacks
