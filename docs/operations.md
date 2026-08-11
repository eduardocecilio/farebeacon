# Operations

## Health semantics

- `/health` proves that the API process can answer and includes its version.
- `/ready` checks PostgreSQL and Redis and returns 503 when either is unavailable.
- `/version` exposes build identity without dependency checks.

Worker health and backlog metrics are not yet part of readiness.

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

## Ephemeral Docker acceptance boundary

The current Compose file is a local acceptance stack, not a production promotion. Running it on a
remote Docker host for acceptance does not make that host a deployment target; remove containers,
networks, volumes, scanner caches, and temporary credentials after the test. A permanent deployment
requires a separately reviewed stack with managed secrets, external volumes, backups, private data
networks, resource sizing, and live post-deploy checks.

## Vercel

The complete system is not suitable for Vercel alone because it requires persistent Celery workers,
Beat, Redis, PostgreSQL, and later isolated browser automation. A supported hybrid topology would
need a dedicated serverless ASGI entrypoint plus externally hosted PostgreSQL/Redis and a separate
worker platform. Those pieces and their production review are not part of this release.
