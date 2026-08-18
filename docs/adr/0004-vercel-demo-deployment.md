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
- PostgreSQL comes from a managed provider. Migrations and seeding run as explicit operations, never
  inside a request.
- The demo keeps `FAREBEACON_NOTIFICATION_BACKEND=disabled`.

If Vercel Queues proves unsuitable, setting `FAREBEACON_CELERY_TASK_ALWAYS_EAGER=true` runs the same
tasks inline. That fallback is a configuration change, not a code change.

## Consequences

- the demo is a reduced deployment, not a promotion of the project to production;
- Telegram delivery is off on the demo on purpose: a public URL with a live bot would let any
  visitor push messages into a private chat;
- the artifact store writes to the function's temporary filesystem, so raw artifacts do not survive
  an instance; a durable deployment needs the S3-compatible adapter that is already in the backlog;
- scheduled evaluation is not equivalent: platform cron is coarse compared to Celery Beat, so demo
  data changes when someone runs the seeding operation, not continuously;
- the demo's isolation is weaker than the Compose stack's, where only `notification-worker` holds
  the bot token and reaches the internet. Every function in a serverless project shares the same
  environment, which is another reason notifications stay disabled there.
