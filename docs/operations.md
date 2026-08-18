# Operations

## Health semantics

- `/health` proves that the API process can answer and includes its version.
- `/ready` checks PostgreSQL and Redis and returns 503 when either is unavailable.
- `/version` exposes build identity without dependency checks.

Worker health and backlog metrics are not yet part of readiness.

## Alert delivery

Alert evaluation runs when a search reaches `succeeded` or `partially_succeeded`. The cheapest
observation is evaluated once per active rule. `new_historical_low` requires a previous successful
observation; `price_below_limit` may match the first run. A sent event starts the rule cooldown.

Delivery states are visible through `GET /api/v1/alerts`:

- `pending`: persisted and awaiting a notification worker;
- `sending`: claimed before the external request;
- `sent`: accepted by Telegram;
- `failed`: provider request failed and needs explicit operator review;
- `suppressed`: cooldown active or the notification backend was disabled.

Only `pending` events are automatically re-enqueued. Do not blindly replay `sending` events: a worker
may have crashed after Telegram accepted the message but before PostgreSQL recorded the response.

## Migrations

`docker compose up` starts the one-shot `migrate` service. Manual execution is:

```bash
docker compose run --rm migrate
```

Never run two schema migrations concurrently. Back up PostgreSQL before applying a migration to an
existing deployment.

## Data and backup scope

Back up:

- PostgreSQL, which owns monitors, runs, normalized entities, and history;
- the artifact volume, if raw diagnostic retention matters;
- deployment secret configuration through the environment's secret manager.

Redis is a broker/cache, not the source of truth. The local Compose volumes are developer-friendly;
a production deployment should map durable data to explicitly managed external volumes.

The Telegram bot token belongs in the deployment secret manager. It is injected only into
`notification-worker`; never place it in monitor payloads, API requests, logs, or source
configuration. Rotate it through `@BotFather` if it is exposed.

## Ephemeral Docker acceptance boundary

The current Compose file is a local acceptance stack, not a production promotion. Running it on a
remote Docker host for acceptance does not make that host a deployment target; remove containers,
networks, volumes, scanner caches, and temporary credentials after the test. A permanent deployment
requires a separately reviewed stack with managed secrets, external volumes, backups, private data
networks, resource sizing, and live post-deploy checks.

## Vercel

A reduced public demo runs on Vercel: the API on the Python runtime, Celery tasks as queue-triggered
functions, and PostgreSQL from a managed provider. It is configuration only, and the procedure is in
[the demo deployment guide](vercel-demo.md).

That deployment is a demo, not a production promotion. It has no persistent worker process, no
Celery Beat, no durable artifact store, and no per-service secret isolation, and it deliberately runs
with notifications disabled. A self-hosted deployment that owns real monitors, real history, and
real Telegram delivery should run the Compose topology, and later isolated browser automation
requires it. See [ADR 0004](adr/0004-vercel-demo-deployment.md).
