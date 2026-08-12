# Architecture

FareBeacon is a single-tenant, self-hosted application whose only public integration boundary is the
HTTP API. The web interface planned for a later phase must consume the same API.

## Dependency direction

```text
API and tasks -> application services -> domain ports and types
                                      <- infrastructure adapters
```

The domain does not import FastAPI, Celery, SQLAlchemy, Redis, Playwright, or provider SDKs.

## Search flow

1. `POST /api/v1/monitors/{id}/runs` persists a queued `SearchRun`.
2. The orchestration task creates one `SourceRun` for every enabled monitor source.
3. Each source task builds one `SearchQuery` per paired date window and calls `SearchSource.fetch()`.
4. Raw batches move to the `normalize` queue.
5. The paired parser produces `NormalizedOffer` instances.
6. Domain validation rejects malformed or incoherent offers.
7. A versioned canonical hash correlates equivalent itineraries across sources.
8. `Itinerary`, `Quote`, and `QuoteObservation` are persisted separately.
9. The final source task calculates `succeeded`, `partially_succeeded`, or `failed` without deleting
   valid observations from other sources.
10. A successful or partially successful run evaluates each active alert rule against its cheapest
    observation and persists an idempotent `AlertEvent` in the same transaction as finalization.
11. Pending events move through the isolated `notifications` queue. The delivery task claims an
    event before calling Telegram, so a Celery replay cannot send it twice.

Celery provides at-least-once delivery. Database uniqueness constraints and effect checks make task
repetition safe; FareBeacon does not claim exactly-once delivery.

## Date windows

`departure_dates` and `return_dates` pair by array index. A one-way monitor omits `return_dates`. A
round-trip monitor must provide exactly one later return date for every departure date. FareBeacon
never creates an implicit Cartesian product.

## Correlation

The `v1` itinerary hash includes ordered leg/segment identity, normalized UTC times, route, airline,
and flight number. It excludes source, price, booking URL, and observation time. Changing the
algorithm requires a new version prefix and a migration strategy.

## Persistence model

- `Monitor` stores a recurring search intention.
- `MonitorSource` stores source selection, priority, and source-scoped configuration.
- `SearchRun` and `SourceRun` preserve asynchronous execution state.
- `Itinerary` is the source-independent flight identity.
- `Quote` is a source-specific current commercial offer.
- `QuoteObservation` is immutable price history for a run.
- `RawArtifact` references bytes in an artifact store; large bytes never live in PostgreSQL.
- `IdempotencyRecord` binds a command key to its request digest and created resource.

`AlertRule` stores the condition. `AlertEvent` stores the selected observation, rendered message,
cooldown suppression, provider, attempt count, and terminal delivery state. A periodic reconciliation
task re-enqueues only `pending` events that were persisted before a broker interruption. It does not
automatically retry `failed` or indeterminate `sending` events because Telegram has no idempotency
key; preferring an explicit reconciliation avoids duplicate user messages after an ambiguous crash.

The domain owns a small `Notifier` port. `FakeNotifier` supplies deterministic tests and
`TelegramNotifier` is the only real adapter. See
[ADR 0003](adr/0003-telegram-only-notifications.md).
