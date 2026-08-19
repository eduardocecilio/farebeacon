# Explicit backlog

These items are intentionally outside the first delivery:

- complete licensed airport and metro-code catalogue behind an `AirportCatalog` port;
- PATCH, pause, resume, cancel, deletion, quote detail, and remaining source administration routes;
- transactional outbox or equivalent broker-dispatch reconciliation;
- quota, cache, reserve, and rate-limit enforcement;
- idempotency-record and artifact-retention cleanup;
- explicit retry/reconciliation commands for failed or stale notification deliveries;
- secure one-time Telegram chat linking for a future web interface;
- interactive slices of the interface: starting a run, creating a monitor, pausing one;
- metrics, worker heartbeat, backlog visibility, and tracing;
- S3/MinIO artifact adapter;
- first approved structured flight API;
- approved HTTP scraper and its legal/contract fixtures;
- isolated Playwright worker and egress policy;
- multi-user authentication and authorization, if FareBeacon becomes a hosted service.

GOWA, WhatsApp Web session gateways, and other unofficial WhatsApp adapters are intentionally not in
the backlog. Telegram is the project's only planned real notification channel.

No real source should start until the MockSource acceptance flow remains green in CI and the target
provider has a documented access policy.
