# Changelog

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
