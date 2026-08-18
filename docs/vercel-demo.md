# Public demo deployment

This guide deploys FareBeacon as a free, read-only public demo on Vercel. It is not a production
deployment; read [ADR 0004](adr/0004-vercel-demo-deployment.md) for what the demo trades away.

The Compose stack remains the reference topology. Nothing in this guide changes it.

## What the demo serves

- the OpenAPI document and Swagger UI at `/docs` and `/openapi.json`;
- `GET` access to monitors, runs, offers, price history, alerts, and sources without a token;
- seeded MockSource data with a real price drop, so price history has more than one point and one
  `new_historical_low` alert exists.

Writes still require the Bearer token, and notifications stay disabled.

## 1. Provision PostgreSQL

Create a managed PostgreSQL database and copy its connection string. Prefer the provider's pooled
endpoint: serverless functions open connections from many short-lived instances.

The URL must use the driver this project installs:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

## 2. Create the Vercel project

Import the repository. The Python runtime resolves the entrypoints from `pyproject.toml`:

- `[tool.vercel] entrypoint = "app:app"` serves the API;
- `[[tool.vercel.subscribers]] entrypoint = "worker:app"` becomes the private, queue-triggered
  function that runs Celery tasks.

Both files put `src` on the import path and re-export the objects that already exist in
`src/farebeacon`. There is no separate serverless codebase.

## 3. Configure the environment

| Variable | Value | Why |
| --- | --- | --- |
| `FAREBEACON_API_TOKEN` | a fresh 32+ character random token | authorizes writes; keep it private |
| `FAREBEACON_DATABASE_URL` | the pooled PostgreSQL URL | the demo's only durable state |
| `FAREBEACON_CELERY_BROKER_URL` | `vercel://` | Celery publishes to Vercel Queues |
| `FAREBEACON_CELERY_RESULT_BACKEND` | `vercel-runtime-cache://` | short-lived task state |
| `FAREBEACON_DEMO_READ_ONLY` | `true` | anonymous reads, authenticated writes |
| `FAREBEACON_NOTIFICATION_BACKEND` | `disabled` | never message a private chat from a public URL |
| `FAREBEACON_ARTIFACTS_ROOT` | `/tmp/farebeacon-artifacts` | the function filesystem is read-only outside `/tmp` |
| `FAREBEACON_ENV` | `demo` | keeps the environment honest in `/health` and logs |

Do not set `FAREBEACON_REDIS_URL`: there is no Redis in this deployment, and readiness no longer
asks for one when the broker does not need it.

## 4. Migrate and seed

Schema changes and seeding never run inside a request. Both run as an explicit operation through the
**Demo database** workflow, which needs one repository secret:

- `DEMO_DATABASE_URL`: the same PostgreSQL URL configured in Vercel.

Run the workflow from the Actions tab. It builds the runtime image, applies `alembic upgrade head`,
and optionally seeds the demo monitors. Seeding is idempotent: running it again returns the existing
monitors instead of duplicating them.

## 5. Verify the deployment

```bash
DEMO_URL='https://your-project.vercel.app'
curl -sS "$DEMO_URL/health"
curl -sS "$DEMO_URL/ready"
curl -sS "$DEMO_URL/api/v1/monitors" | jq '.data.total'
curl -sS "$DEMO_URL/api/v1/alerts" | jq '[.data.items[].rule_type] | unique'
```

`/ready` must report `database: ok` and no Redis check. `/api/v1/monitors` must answer 200 without an
`Authorization` header, and any `POST` must answer 401 without one.

## If Vercel Queues does not work out

Vercel Queues is a public beta. If task delivery misbehaves, the demo can run every task inline:

1. set `FAREBEACON_CELERY_TASK_ALWAYS_EAGER=true`;
2. clear `FAREBEACON_CELERY_BROKER_URL` and `FAREBEACON_CELERY_RESULT_BACKEND`;
3. redeploy.

Readiness, delivery states, and the API contract stay the same. The trade is that a run executes
inside the request that starts it, so it must finish within the function's maximum duration.

## Known limits of the demo

- raw artifacts land in the function's temporary filesystem and do not survive an instance;
- scheduled evaluation is coarse; the demo's data moves when the seeding operation runs, not
  continuously;
- serverless functions share one environment, so the Compose stack's isolation of the notification
  worker does not exist here;
- free plans cap function duration, so a source that is slower than MockSource would need the
  Compose topology or a longer duration.
