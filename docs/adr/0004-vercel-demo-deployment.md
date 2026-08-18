# ADR 0004: The public demo runs on Vercel with a reduced scope

Status: accepted

## Context

FareBeacon's reference topology is the Compose stack: an API, a scheduler, four workers, PostgreSQL,
and Redis. That topology is the point of the project, and it is what a self-hosted deployment
should run.

A public demo has a different goal. It has to be reachable from a link, cost nothing, and never
become a dependency of anything real. It cannot run on a personal server, because a showcase must
not put a working machine at risk.

Vercel runs ASGI applications on its Python runtime and, through Vercel Queues, runs Celery tasks as
queue-triggered functions instead of long-lived worker processes. That makes the asynchronous
architecture survive the move rather than collapsing into inline execution.

## Decision

The demo deploys the same code with configuration only.

- `FAREBEACON_CELERY_BROKER_URL` and `FAREBEACON_CELERY_RESULT_BACKEND` replace Redis with the
  platform broker. Both default to `FAREBEACON_REDIS_URL`, so the Compose stack is untouched.
- The Celery queues are declared in `task_queues`, not only in `task_routes`, because a build
  discovers subscribers by importing the application and reading its declared queues.
- `/ready` reports Redis only when the broker or the result backend needs it.
- `FAREBEACON_DEMO_READ_ONLY` answers `GET`, `HEAD`, and `OPTIONS` without a token. Every write still
  requires the Bearer token, so no write credential is published.
- The demo carries its own database. The build command applies the real Alembic schema to a SQLite
  file and seeds it; the function copies that file into its temporary directory at startup. No
  managed database, account, or credential is involved, and every deployment rebuilds the data.
- Migrations and seeding are build or workflow operations. Neither ever runs inside a request.
- The demo keeps `FAREBEACON_NOTIFICATION_BACKEND=disabled`.

The bundled database is per-instance, so the demo runs tasks inline rather than through a queue.
Setting `FAREBEACON_DATABASE_URL` to a managed PostgreSQL instance makes it inert and lets the queue
path run for real. Both are configuration, not code.

## Consequences

- the demo is a reduced deployment, not a promotion of the project to production;
- Telegram delivery is off on the demo on purpose: a public URL with a live bot would let any
  visitor push messages into a private chat;
- the artifact store writes to the function's temporary filesystem, so raw artifacts do not survive
  an instance; a durable deployment needs the S3-compatible adapter that is already in the backlog;
- the demo's data changes when a deployment rebuilds it, not continuously, because there is no
  Celery Beat and no long-lived scheduler;
- writes do not survive a function instance while the bundled database is in use, which is
  acceptable only because the demo is read-only for visitors;
- the demo's isolation is weaker than the Compose stack's, where only `notification-worker` holds
  the bot token and reaches the internet. Every function in a serverless project shares the same
  environment, which is another reason notifications stay disabled there.
