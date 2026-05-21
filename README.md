# brime — Python SDK

Official Python SDK for the [Brime API](https://brime.dev) — search, extract, and research the web with a single key.

```bash
pip install brime
```

## Quickstart

### Search

```python
from brime import Brime

client = Brime(api_key="sk-brime-...")
result = client.search("BM25 ranking algorithm")

print(result.answer)
for r in result.results:
    print(f"- {r.title}  {r.url}")
```

### Extract

```python
result = client.extract(["https://example.com", "https://en.wikipedia.org/wiki/BM25"])

for r in result.results:
    print(r.url, r.method, len(r.markdown))
for f in result.failed:
    print("FAIL", f.url, f.error.code, f.error.message)
```

### Research (basic — synchronous)

```python
result = client.research("what is the okapi bm25 formula", depth="basic")
print(result.answer)
print(f"Sources: {len(result.sources)}")
```

### Research (deep — wait for completion)

```python
result = client.research(
    "compare frontier coding models with concrete benchmark numbers",
    depth="deep",
    wait=True,             # block until terminal
    poll_interval=10,      # seconds between status polls
    poll_timeout=420,      # seconds total
)
print(result.status)        # "complete" | "errored" | "timeout"
print(result.answer)
print(f"Sources: {result.sources_count}, rounds: {result.current_round}")
```

## Authentication

Pass `api_key=` directly **or** set the `BRIME_API_KEY` environment variable:

```bash
export BRIME_API_KEY="sk-brime-..."
```

```python
from brime import Brime
client = Brime()                        # uses BRIME_API_KEY
client = Brime(api_key="sk-brime-...")  # explicit override
```

Override the base URL (for staging/preview):

```python
client = Brime(base_url="https://brime-api-preview.turanalp5645.workers.dev")
# or via env: BRIME_BASE_URL=https://...
```

## Async

Every method is mirrored on `AsyncBrime`:

```python
import asyncio
from brime import AsyncBrime

async def main():
    async with AsyncBrime() as client:
        result = await client.search("python async io")
        print(result.answer)

asyncio.run(main())
```

## Streaming research

```python
for event in client.research_stream("what is BM25", depth="deep"):
    print(event.event, event.data)
    if event.event in ("complete", "error", "timeout"):
        break
```

Async variant:

```python
async with AsyncBrime() as client:
    async for event in client.research_stream("…", depth="deep"):
        print(event.event)
        if event.event == "complete":
            break
```

Resume from a previous stream cursor with `last_event_id="..."` (server replays from that frame onward).

## Search depth

| `depth`     | Behaviour                                                    | Credits |
|-------------|--------------------------------------------------------------|---------|
| `instant`   | SERP snippets, no scrape, no LLM answer (cache-first)        | 0.5     |
| `basic`     | SERP + chunk + BM25 + LLM answer (default)                   | 1       |
| `advanced`  | `basic` + advanced BM25 (Lv & Zhai 2011) + chunk reranking   | 2       |

Common filters work on every depth:

```python
client.search(
    "tesla earnings",
    depth="advanced",
    topic="finance",
    time_range="week",
    domains=["sec.gov", "investor.tesla.com"],
    exclude_domains=["seekingalpha.com"],
    max_results=10,
)
```

## Error handling

Every Brime error inherits from `BrimeError`:

```python
from brime import (
    Brime,
    BrimeError,
    AuthenticationError,
    RateLimitError,
    InsufficientCreditsError,
    InvalidRequestError,
    NotFoundError,
    UpstreamError,
    InternalError,
)

try:
    client.search("…")
except AuthenticationError:
    print("Bad API key")
except RateLimitError:
    print("Slow down")
except InsufficientCreditsError:
    print("Top up at brime.dev/billing")
except BrimeError as e:
    print(f"{e.code} (HTTP {e.status}): {e}")
```

## Idempotency

`/v1/extract` and `/v1/research` (deep mode) require an `Idempotency-Key`. The SDK auto-generates a UUID4 per call, so retries against the same call site won't double-charge. Override with `idempotency_key="..."` when you want explicit deduplication across processes:

```python
client.extract(["https://x"], idempotency_key="my-stable-key-2026-05-06")
```

## Configuration reference

| Constructor arg | Env var          | Default                    |
|-----------------|------------------|----------------------------|
| `api_key`       | `BRIME_API_KEY`  | — (required)               |
| `base_url`      | `BRIME_BASE_URL` | `https://api.brime.dev`     |
| `timeout`       | —                | `30.0` seconds             |

Per-call timeouts override the constructor: `client.search("…", timeout=60)`.

## Compatibility

- Python 3.9+
- Sync (`Brime`) and async (`AsyncBrime`) — fully type-annotated, ships with `py.typed`
- Single dependency tree: `httpx>=0.27` and `pydantic>=2.6`

## Drop-in clients

Already using a different vendor's SDK? Brime exposes wire-compatible adapters under separate paths so the official SDKs work unchanged:

- Tavily — `TavilyClient(api_key, api_base_url="https://api.brime.dev/tavily")`
- Exa — `Exa(api_key=..., base_url="https://api.brime.dev/exa")`
- Parallel — `Parallel(api_key, base_url="https://api.brime.dev/parallel")`

Use those when migrating; reach for `brime` (this SDK) when starting fresh or wanting Brime-native ergonomics (deep research, SSE replay, depth presets).

## License

MIT © Brime
