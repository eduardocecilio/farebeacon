# Public demo deployment

This guide deploys FareBeacon as a free, read-only public demo on Vercel. It is not a production
deployment; read [ADR 0004](adr/0004-vercel-demo-deployment.md) for what the demo trades away.

The Compose stack remains the reference topology. Nothing here changes it.

## What the demo serves

- a read-only interface at `/`: monitors, price history with the observed trend, normalized
  offers, and alert delivery state;
- the OpenAPI document and Swagger UI at `/docs` and `/openapi.json`;
- `GET` access to monitors, runs, offers, price history, alerts, and sources without a token;
- seeded MockSource data with a real price drop, so price history has more than one point and one
  `new_historical_low` alert exists.

Writes still require the Bearer token, and notifications stay disabled.

## Where the data comes from

The demo ships its own database. `build_demo_db.py` runs as the Vercel build command: it creates a
SQLite file from the SQLAlchemy models, seeds the deterministic monitors, and leaves `demo.db` inside
the deployment bundle. At startup the function copies that file into its temporary directory, which
is the only writable path, and points the application at the copy.

The schema comes from the models, the same way the test suite builds its database. Alembic remains
the path for a PostgreSQL deployment, where migrations run as an explicit operation.

If the bundled file never reaches the function, the first boot builds and seeds the database in the
temporary directory instead. The demo therefore does not depend on a build artifact surviving the
packaging step, and the build itself boots the entrypoint both ways before shipping.

That is the whole setup. No managed database, no account, no credential, and no cost. Every
deployment rebuilds the data, so the demo cannot drift or fill up.

The trade is that each function instance holds its own copy: writes do not survive an instance and
are not shared between them. The demo is read-only for visitors, so this is invisible to them, but
it is why the demo runs Celery tasks inline instead of through a queue. To deploy with durable
shared state, see [durable state](#durable-state-optional).

## 1. Create the Vercel project

Import the repository. The Python runtime resolves everything from `pyproject.toml`:

- `[tool.vercel] entrypoint = "app:app"` serves the API;
- `[tool.vercel.scripts] build` builds the bundled demo database.

`app.py` puts `src` on the import path and re-exports the application that already exists in
`src/farebeacon`. There is no separate serverless codebase.

## 2. Configure nothing

The demo needs no environment variable. Running on the bundled, disposable database is what makes a
deployment a demo, so the entrypoint carries that posture by itself:

- reads are public;
- writes are refused, because no API token exists to authorize them;
- notifications are disabled;
- tasks run inline, since a per-instance database cannot be shared with a worker.

That is stronger than a configured demo, not weaker: there is no write credential to leak, rotate,
or accidentally publish. Every value remains overridable by setting the matching variable, and a
deployment that configures its own database gets none of these defaults.

Do not import `.env.example`: it configures the Compose stack, and the platform rejects reserved
names such as `TZ` with `Environment variable "TZ" is invalid`. No timezone variable is needed,
because the application is UTC everywhere.

Set `FAREBEACON_API_TOKEN` only if you want an authenticated writer on the demo. It must then be
available at build time, because the build boots the application before shipping it.

## 3. Verify the deployment

```bash
DEMO_URL='https://your-project.vercel.app'
curl -sS "$DEMO_URL/health"
curl -sS "$DEMO_URL/ready"
curl -sS "$DEMO_URL/api/v1/monitors" | jq '.data.total'
curl -sS "$DEMO_URL/api/v1/alerts" | jq '[.data.items[].rule_type] | unique'
```

`/ready` must report `database: ok` and no Redis check. `/api/v1/monitors` must answer 200 without an
`Authorization` header, and any `POST` must answer 401 without one.

## Durable state (optional)

A deployment that needs shared, surviving state replaces the bundled database with a managed
PostgreSQL instance. Prefer the provider's pooled endpoint: serverless functions open connections
from many short-lived instances.

```text
postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

Set `FAREBEACON_DATABASE_URL` to that value, which makes the bundled database inert. Then the
asynchronous pipeline can run for real instead of inline:

1. set `FAREBEACON_CELERY_BROKER_URL=vercel://` and
   `FAREBEACON_CELERY_RESULT_BACKEND=vercel-runtime-cache://`;
2. uncomment the `[[tool.vercel.subscribers]]` block in `pyproject.toml`, which compiles `worker.py`
   into a private, queue-triggered function that only Vercel Queues can invoke;
3. add the `DEMO_DATABASE_URL` repository secret and run the **Demo database** workflow, which
   applies migrations and seeds outside any request.

Schema changes and seeding never run inside a request in either mode.

## Known limits of the demo

- raw artifacts land in the function's temporary filesystem and do not survive an instance;
- the seeded data changes when a deployment rebuilds it, not continuously;
- serverless functions share one environment, so the Compose stack's isolation of the notification
  worker does not exist here;
- free plans cap function duration, so a source slower than MockSource would need the Compose
  topology or a longer duration.
