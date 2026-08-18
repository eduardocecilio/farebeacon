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
- price-limit and new-historical-low alert evaluation
- one alert candidate per rule and run, with a 24-hour default cooldown
- auditable notification state and delivery attempts
- optional Telegram delivery through a dedicated egress worker
- local raw-artifact storage behind a storage port
- Celery Beat scheduling for due monitors
- public liveness, readiness, and version endpoints

No real flight source, scraping, Playwright, WhatsApp integration, booking, payment, or ticket
issuance is included.

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
                                      |
                                      v
                              evaluate alert rules
                                      |
                                      v
                         notifications queue -> Telegram
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

## Telegram notifications

Telegram is the only real notification channel supported by FareBeacon. It uses Telegram's official
Bot API and does not link a personal Telegram account or phone session to FareBeacon. The account
used with `@BotFather` only creates and administers the bot.

1. Create a bot with `@BotFather` and store the generated token as a secret.
2. Open the new bot from the destination Telegram account and press **Start** once.
3. Obtain that private chat's numeric `chat_id` from the bot's updates.
4. Configure:

```dotenv
FAREBEACON_NOTIFICATION_BACKEND=telegram
FAREBEACON_TELEGRAM_BOT_TOKEN=replace-with-the-bot-token
FAREBEACON_TELEGRAM_CHAT_ID=replace-with-the-chat-id
```

The token is passed only to `notification-worker`. That worker is the only application service on
the egress network. With the default `FAREBEACON_NOTIFICATION_BACKEND=disabled`, matching events are
recorded as `suppressed` and no external request is made. `fake` exists for automated tests and is
rejected in production.

The default cooldown is 1,440 minutes and can be changed globally with
`FAREBEACON_DEFAULT_ALERT_COOLDOWN_MINUTES`. Evaluation chooses the cheapest observation in each run,
so a source returning several matching offers does not send a burst of equivalent alerts. The first
successful run establishes the historical baseline; `new_historical_low` starts comparing on later
runs.

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

curl -sS "http://127.0.0.1:8000/api/v1/alerts?monitor_id=$MONITOR_ID" \
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
make lock  # only after changing dependency declarations
docker compose logs -f --tail=200
docker compose down
```

The test suite includes unit, source-contract, integration, and end-to-end coverage. It uses SQLite
and eager Celery only for test isolation; the runtime acceptance path uses PostgreSQL, Redis, and
independent workers.

## Deployment

The Compose stack is the reference topology, and a self-hosted deployment should run it. See
[docs/operations.md](docs/operations.md) for backup scope, secret handling, and the acceptance
boundary.

A reduced public demo can also run on Vercel, with no database service, account, or cost: the build
command seeds a SQLite database into the deployment bundle, and the function copies it into its
temporary directory at startup. The demo answers reads without a token, requires the token for every
write, and keeps notifications disabled. It deploys the same code through configuration alone —
there is no separate serverless codebase, and pointing `FAREBEACON_DATABASE_URL` at a managed
PostgreSQL instance upgrades it to durable state with a queue-backed worker. See
[docs/vercel-demo.md](docs/vercel-demo.md) and
[ADR 0004](docs/adr/0004-vercel-demo-deployment.md) for what it trades away.

## Source policy

New sources must be explicitly reviewed for terms of use, rate limits, data licensing, and technical
access rules. FareBeacon does not bypass CAPTCHA, authentication, paywalls, robots controls, or other
protections. See [docs/sources.md](docs/sources.md) and [SECURITY.md](SECURITY.md).

GOWA and other WhatsApp Web session gateways are intentionally outside the project and its roadmap.
See [ADR 0003](docs/adr/0003-telegram-only-notifications.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
