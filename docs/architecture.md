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

Alert tables are present so later phases do not require changing the historical quote model, but no
notifier is active in this release.

