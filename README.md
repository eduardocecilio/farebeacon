# FareBeacon

FareBeacon is an open-source, agent-friendly airfare monitoring hub. It accepts results from
independent acquisition sources, normalizes and validates them, correlates equivalent itineraries,
preserves price observations, and exposes the entire workflow through a versioned HTTP API.

The first release is deliberately offline: `MockSource` proves the complete workflow without an
external provider, scraper, browser, account, or API key.

## What works in this delivery

- Bearer-authenticated FastAPI under `/api/v1`
- complete OpenAPI document at `/openapi.json`
- monitor creation with idempotency
- asynchronous manual runs with Celery
- one `SourceRun` per selected source
- deterministic direct and connecting mock flights
- separate acquisition and normalization queues
- offer validation, itinerary correlation, and quote deduplication
- PostgreSQL-backed current quotes and observation history
- partial success when one source fails
- local raw-artifact storage behind a storage port
- Celery Beat scheduling for due monitors
- public liveness, readiness, and version endpoints

No real flight source, scraping, Playwright, notification, booking, payment, or ticket issuance is
included.

## Architecture

```text
client / agent
      |
      v
FastAPI ---- PostgreSQL
      |
      v
orchestration queue
      |
      v
source.mock queue -> raw source batches
      |
      v
normalize queue -> validate -> correlate -> persist -> history
```

`SearchSource.fetch()` only acquires source-shaped data. Its paired `SourceParser` produces the
provider-independent `NormalizedOffer`. A source cannot write itineraries or quotes directly.

See [docs/architecture.md](docs/architecture.md) and
[ADR 0001](docs/adr/0001-separate-acquisition-and-normalization.md).

## Requirements

- Docker Engine with Compose v2
- `curl` for the examples

Python, PostgreSQL, Redis, Ruff, pytest, and Alembic run inside containers. Nothing needs to be
installed globally.

## Start locally

```bash
cp .env.example .env
```

Replace both `change-me` values in `.env`. A token can be generated with a password manager or:

```bash
openssl rand -hex 32
```

Then start the stack:

```bash
docker compose up --build -d
docker compose ps
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

The one-shot `migrate` service applies Alembic migrations before the API and workers start.
PostgreSQL and Redis are not published on host ports.

## Authentication

All `/api/v1` endpoints require the token from `FAREBEACON_API_TOKEN`:

```bash
export FAREBEACON_TOKEN='the-value-from-your-env-file'
```

Tokens are compared in constant time and are never returned by the API. Do not pass tokens in query
strings.

## Complete BSB to PVH example

Create a monitor:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/monitors \
  -H "Authorization: Bearer $FAREBEACON_TOKEN" \
  -H "Idempotency-Key: monitor-bsb-pvh-v1" \
  -H 'Content-Type: application/json' \
  --data @- <<'JSON'
{
  "name": "Brasília para Porto Velho",
  "route": {"origin": "BSB", "destination": "PVH"},
  "departure_dates": ["2030-07-10", "2030-07-11"],
  "passengers": {"adults": 1, "children": 0, "infants": 0},
  "filters": {"currency": "BRL", "max_stops": 1, "max_price_minor": 100000},
  "sources": ["mock"],
  "schedule": {"interval_minutes": 720},
  "alerts": {"new_historical_low": true, "price_below_minor": 100000}
}
JSON
```

Copy `data.id`, then start a run. The API returns immediately with `queued`:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/monitors/$MONITOR_ID/runs" \
  -H "Authorization: Bearer $FAREBEACON_TOKEN" \
  -H 'Idempotency-Key: first-manual-run'
```

```json
{
  "data": {"run_id": "run_...", "status": "queued"},
  "meta": {"request_id": "req_..."}
}
```

Poll the run and query results:

```bash
curl -sS "http://127.0.0.1:8000/api/v1/runs/$RUN_ID" \
  -H "Authorization: Bearer $FAREBEACON_TOKEN"

curl -sS "http://127.0.0.1:8000/api/v1/monitors/$MONITOR_ID/offers" \
  -H "Authorization: Bearer $FAREBEACON_TOKEN"

curl -sS "http://127.0.0.1:8000/api/v1/monitors/$MONITOR_ID/price-history" \
  -H "Authorization: Bearer $FAREBEACON_TOKEN"
```

Repeating either POST with the same `Idempotency-Key` and the same body returns the original
resource. Reusing the key with a different body returns `IDEMPOTENCY_CONFLICT`.

## Development commands

```bash
make lint
make typecheck
make test
make openapi
docker compose logs -f --tail=200
docker compose down
```

The test suite includes unit, source-contract, integration, and end-to-end coverage. It uses SQLite
and eager Celery only for test isolation; the runtime acceptance path uses PostgreSQL, Redis, and
independent workers.

## Deployment

The full stack needs long-running workers and a scheduler, so it is designed for Docker hosts such
as a small server or homelab. Vercel is not a target for the complete application. See
[docs/operations.md](docs/operations.md) before promoting it beyond local development.

## Source policy

New sources must be explicitly reviewed for terms of use, rate limits, data licensing, and technical
access rules. FareBeacon does not bypass CAPTCHA, authentication, paywalls, robots controls, or other
protections. See [docs/sources.md](docs/sources.md) and [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
