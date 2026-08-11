# FareBeacon implementation plan

## Product objective

Build an open-source hub that monitors airfare offers from multiple independently implemented
sources. Every source passes through acquisition, parsing, normalization, validation, correlation,
persistence, history, alert evaluation, and notification boundaries.

The only public integration surface is the FastAPI HTTP API. Agents, scripts, and the future Jinja2
and HTMX interface use that API. FareBeacon has no product CLI.

## Non-negotiable boundaries

- Monetary domain values use `Decimal`; persistence uses integer minor units with a currency
  exponent table.
- Source code cannot write itinerary, quote, or observation tables.
- Long work runs asynchronously and preserves valid partial results.
- Command POSTs and all Celery effects are idempotent.
- Raw large artifacts stay outside PostgreSQL behind an artifact-store port.
- No payment data, purchase, issuance, access-control bypass, CAPTCHA bypass, or invented provider
  contract.
- No real source begins until the offline MockSource vertical slice is green.

## Source contracts

```python
class SearchSource(Protocol):
    name: str
    kind: SourceKind
    version: str
    capabilities: SourceCapabilities

    async def healthcheck(self) -> bool: ...
    async def estimate_cost(self, query: SearchQuery) -> int: ...
    async def fetch(self, query: SearchQuery, context: SourceExecutionContext) -> SourceBatch: ...


class SourceParser(Protocol):
    source_name: str
    version: str

    def normalize(
        self,
        item: RawSourceItem,
        *,
        query: SearchQuery,
        observed_at: datetime,
    ) -> Sequence[NormalizedOffer]: ...
```

## First delivery

The first delivery contains Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis,
Celery, Celery Beat, HTTPX, Jinja2 as a future web dependency, pytest, Ruff, Docker, and Compose.

Services are `api`, `scheduler`, `orchestration-worker`, `mock-worker`, `normalization-worker`,
`migrate`, `postgres`, and `redis`. Queues are `orchestration`, `source.mock`, `normalize`, and
`maintenance`. HTTP, browser, external, alert, and notification workers appear only when their
features exist; empty workers and Playwright are not shipped as dead scaffolding.

Implemented entities are Monitor, MonitorSource, SearchRun, SourceRun, Itinerary, FlightSegment,
Quote, QuoteObservation, AlertRule, AlertEvent, SourceDefinition, RawArtifact, and IdempotencyRecord.

Implemented API operations:

```text
POST /api/v1/monitors
GET  /api/v1/monitors
GET  /api/v1/monitors/{id}
POST /api/v1/monitors/{id}/runs
GET  /api/v1/runs
GET  /api/v1/runs/{id}
GET  /api/v1/monitors/{id}/offers
GET  /api/v1/monitors/{id}/price-history
GET  /api/v1/sources
GET  /api/v1/sources/{name}
GET  /api/v1/sources/{name}/health
GET  /health
GET  /ready
GET  /version
```

## Acceptance scenario

The primary fixture monitors BSB to PVH on 2030-07-10 and 2030-07-11 with one adult, BRL, at most
one stop, a BRL 1,000.00 threshold, `mock`, a 720-minute schedule, and historical-low/price-limit
rules. The dates are intentionally future-facing for durable public documentation.

Acceptance requires:

1. Compose builds and starts after `.env` is configured.
2. Alembic creates the schema before the API starts.
3. Health and readiness pass.
4. Monitor creation returns the same resource on an idempotent replay.
5. A run initially returns `queued`.
6. Independent Celery workers acquire and normalize MockSource data.
7. The run reaches `succeeded` or `partially_succeeded` according to source outcomes.
8. Offers and observation history are queryable.
9. Duplicate items do not create duplicate observations for a source run.
10. Ruff, tests, OpenAPI generation, and secret checks pass.

## Later phases

1. Complete monitor/run/source administration API.
2. Jinja2 and HTMX web interface consuming the API.
3. Alert evaluation, FakeNotifier, then Telegram.
4. Quota, cost, cache, reserve, and rate limiting.
5. First approved structured API after its official contract is reviewed.
6. Amadeus sandbox and production adapters with explicit test-data labeling.
7. First legally reviewed HTTP parser with static fixtures.
8. Isolated Playwright worker with no direct database access.

The detailed backlog lives in `docs/TODO.md`. A code-complete release and a production promotion are
separate decisions.

