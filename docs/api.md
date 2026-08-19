# API conventions

## Base path and authentication

Application operations use `/api/v1` and Bearer authentication. `/health`, `/ready`, `/version`,
`/docs`, and `/openapi.json` are public. The root redirects to `/docs`, because the API has no
representation of its own root.

## Envelopes

Successful responses use:

```json
{"data": {}, "meta": {"request_id": "req_..."}}
```

Errors use:

```json
{
  "error": {
    "code": "MONITOR_NOT_FOUND",
    "message": "Monitor not found.",
    "details": {"monitor_id": "mon_..."}
  },
  "meta": {"request_id": "req_..."}
}
```

The response also returns `X-Request-ID`. A caller-supplied value is preserved only when it matches
the documented safe character and length policy.

## Idempotency

`POST /api/v1/monitors` and `POST /api/v1/monitors/{id}/runs` require `Idempotency-Key`.
The uniqueness scope includes the HTTP operation. Replaying the same key and request returns the
same resource; a different request returns HTTP 409 with `IDEMPOTENCY_CONFLICT`.

Records expire logically after seven days. Physical cleanup belongs to the maintenance phase.

## Pagination

List operations accept one-based `page` and `page_size` from 1 to 100. Page data contains `items`,
`page`, `page_size`, and `total`.

## Stable error codes in this release

- `VALIDATION_ERROR`
- `AUTHENTICATION_REQUIRED`
- `MONITOR_NOT_FOUND`
- `RUN_NOT_FOUND`
- `RUN_ALREADY_ACTIVE`
- `ALERT_NOT_FOUND`
- `SOURCE_NOT_FOUND`
- `SOURCE_DISABLED`
- `SOURCE_RATE_LIMITED`
- `SOURCE_QUOTA_EXCEEDED`
- `SOURCE_TEMPORARILY_UNAVAILABLE`
- `SOURCE_CONTRACT_CHANGED`
- `NO_VALID_OFFERS`
- `IDEMPOTENCY_CONFLICT`
- `INTERNAL_ERROR`

The generated OpenAPI document is the authoritative schema.

## Alert events

`GET /api/v1/alerts` lists evaluated alert and delivery state. It accepts the normal pagination
parameters plus optional `monitor_id` and `status` filters. `GET /api/v1/alerts/{id}` returns one
event. These endpoints never expose the Telegram bot token or chat credential.
