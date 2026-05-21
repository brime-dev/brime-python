# brime

[![PyPI](https://img.shields.io/pypi/v/brime.svg?logo=pypi)](https://pypi.org/project/brime/)
[![Python](https://img.shields.io/pypi/pyversions/brime.svg?logo=python)](https://pypi.org/project/brime/)
[![Typed](https://img.shields.io/pypi/types/brime.svg?logo=python)](https://pypi.org/project/brime/)
[![MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

**The live-web toolkit for AI apps.** One API key. One SDK. Search, scrape, and research the open web — clean output, sane defaults, no plumbing.

**[Documentation](https://docs.brime.dev/sdks/python)** | **[Get Your API Key](https://platform.brime.dev/keys)** | **[Changelog](./CHANGELOG.md)** | **[GitHub](https://github.com/brime-dev/brime-python)**

```bash
pip install brime
```

Python 3.9+. Sync and async clients, exponential-backoff retry, `with_raw_response` observability, fully typed (`py.typed`). Single dependency tree: `httpx` + `pydantic`. Released via [npm-style Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — every wheel ships with PyPI provenance.

## Why brime?

- **One key, three primitives.** `search`, `extract`, `research` — the shape every AI app needs from the web.
- **Tuned defaults.** No depth selectors, no round counters, no knobs to babysit. The gateway is tuned for you; you pass a query, you get a clean answer.
- **Drop-in compatible.** Already on Tavily, Exa, or Parallel? Point their SDK at our adapter URL and your code keeps working. Migrate when you're ready.
- **Honest pricing.** Flat per-call credits. 0.5 for search, 1 per URL for extract, 5 for research. No surprises.

## 30 seconds

```python
from brime import Brime

brime = Brime()  # reads BRIME_API_KEY

# Live answer + ranked sources, sub-second.
result = brime.search(query="what changed in the latest TypeScript release")
print(result.answer)
```

That's the whole shape. Same pattern for `extract` and `research`.

## What you can build

### Search the open web

```python
result = brime.search(
    query="tesla earnings",
    topic="finance",       # optional: news / general / finance recency hint
    time_range="week",     # optional: day / week / month / year
    domains=["sec.gov"],   # optional allow-list
)
```

### Turn any URL into clean markdown

```python
result = brime.extract(urls=[
    "https://example.com",
    "https://en.wikipedia.org/wiki/BM25",
])

for r in result.results:
    print(r.url, len(r.markdown))
for f in result.failed:
    print("skipped", f.url, f.error.message)
```

Handles HTML, PDF, DOCX, and JavaScript-heavy SPAs. The smart-clean pipeline strips chrome, nav, cookie banners, and template noise — what's left is the article.

### Multi-step research with citations

```python
result = brime.research(
    query="compare frontier coding models with concrete benchmark numbers",
)

print(result.answer)
print(f"{len(result.sources)} sources cited")
```

One call, ~30–90 seconds, real synthesis from real sources.

Live progress? Stream it:

```python
for evt in brime.research_stream(query="..."):
    print(evt.event, evt.data)
    if evt.event in ("complete", "error", "timeout"):
        break
```

## Authentication

```bash
export BRIME_API_KEY="sk-brime-..."
```

```python
Brime()                        # uses BRIME_API_KEY
Brime(api_key="sk-brime-...")  # explicit
Brime(base_url="https://...")  # staging override (or BRIME_BASE_URL env)
```

Get a key at [brime.dev](https://brime.dev) — the free tier comes with 1,000 credits/month and no card.

## Async

Every method is mirrored on `AsyncBrime`:

```python
import asyncio
from brime import AsyncBrime

async def main():
    async with AsyncBrime() as brime:
        result = await brime.search(query="python async io")
        print(result.answer)

asyncio.run(main())
```

Async streaming works the same way:

```python
async with AsyncBrime() as brime:
    async for evt in brime.research_stream(query="..."):
        if evt.event == "complete":
            print(evt.data)
            break
```

## Error handling

Typed exceptions, predictable surface area:

```python
from brime import (
    BrimeError,
    AuthenticationError,
    RateLimitError,
    InsufficientCreditsError,
)

try:
    brime.search(query="...")
except AuthenticationError:
    ...  # bad key
except RateLimitError:
    ...  # back off
except InsufficientCreditsError:
    ...  # top up
except BrimeError as e:
    print(e.code, e.message)
```

## Idempotency, baked in

`extract` calls require an `Idempotency-Key` — the SDK auto-generates one per call so accidental retries never double-charge. Pin it yourself for cross-process dedup:

```python
brime.extract(
    urls=["https://x"],
    idempotency_key="user-42-prefetch-2026-05",
)
```

## Configuration

| Constructor arg | Env var          | Default                  |
|-----------------|------------------|--------------------------|
| `api_key`       | `BRIME_API_KEY`  | — (required)             |
| `base_url`      | `BRIME_BASE_URL` | `https://api.brime.dev`  |
| `timeout`       | —                | `30.0` seconds           |

Per-call override: `brime.search(query="...", timeout=60)`.

## Already using Tavily, Exa, or Parallel?

You don't have to rip them out. Brime exposes wire-compatible adapters:

```python
TavilyClient(api_key, api_base_url="https://api.brime.dev/tavily")
Exa(api_key=..., base_url="https://api.brime.dev/exa")
Parallel(api_key, base_url="https://api.brime.dev/parallel")
```

Same response shapes, same code. Switch to the native `brime` SDK when you want the extras (research synthesis, SSE streaming, smart-clean extract).

## Links

- Docs — [docs.brime.dev](https://docs.brime.dev)
- API reference — [docs.brime.dev/api-reference](https://docs.brime.dev/api-reference)
- Status — [brime.dev](https://brime.dev)
- Issues — [github.com/brime-dev/brime-python/issues](https://github.com/brime-dev/brime-python/issues)

## License

MIT © Brime
