# Security design

## Current threat model

FareBeacon accepts authenticated monitor commands and untrusted source payloads. Relevant threats
include credential leakage, duplicate commands, parser abuse, malicious URLs, oversized artifacts,
task replay, lateral container movement, and accidental database exposure.

## Implemented controls

- constant-time comparison of the single high-entropy MVP token;
- no token in query parameters, responses, or application logs;
- strict Pydantic request schemas and structured error responses;
- explicit request and source-payload size ceilings;
- scoped idempotency records with request hashes;
- PostgreSQL and Redis have no host port mapping;
- API and workers run non-root with all Linux capabilities dropped;
- PostgreSQL starts as its dedicated non-root user without the root-only `gosu` helper;
- read-only application root filesystems with bounded tmpfs;
- separate source and normalization queues;
- Telegram credentials isolated to a dedicated notification worker and egress network;
- atomic notification claims preventing duplicate sends on ordinary task replay;
- generated, traversal-safe artifact keys and content hashes;
- raw artifacts are not labelled sanitized until an explicit redaction stage exists;
- dependency lockfiles carry hashes; base images and CI actions are immutable references;
- no Docker socket, browser, payment data, passenger identity, or arbitrary execution;
- response headers denying framing and browser capabilities.

## Known MVP limits

- one administrative token means no user-level authorization or audit principal;
- local artifacts have no encryption or retention cleanup yet;
- the static IATA syntax check is not a complete licensed airport/metro-code catalogue;
- Compose resource limits depend on the Docker runtime honoring `deploy.resources`;
- the data plane and MockSource workers use an internal-only network;
- only the API joins a separate ingress bridge, with its host port bound to loopback;
- approved real sources require a separate egress policy.
- Telegram does not provide an idempotency key, so an event left in `sending` after a hard worker
  failure requires explicit reconciliation rather than automatic replay.

## Public demo mode

`FAREBEACON_DEMO_READ_ONLY` exists for one purpose: a public showcase whose database holds only
disposable seeded data. It answers `GET`, `HEAD`, and `OPTIONS` without a token; `POST` and every
other write still require the Bearer token, so no write credential is published.

A demo deployment normally runs with no API token at all. The application then boots read-only and
answers every write with `AUTHENTICATION_REQUIRED`, because there is no credential that could
authorize one. A write path that cannot be unlocked is safer than one protected by a token that has
to be stored, scoped, and rotated.

Enabling it is a decision about the data, not about the endpoint. Do not enable it on a deployment
that owns real monitors or real history, and keep `FAREBEACON_NOTIFICATION_BACKEND=disabled` there:
a public URL with a live bot token would let visitors drive messages into a private chat.

The mode adds no rate limiting of its own. It assumes the hosting platform terminates TLS and
absorbs abusive traffic, which is why [the demo deployment](vercel-demo.md) is described for a
managed platform rather than for a self-hosted port.

Outside that mode, never expose this alpha directly to the public internet without a reverse proxy,
TLS, rate limiting, secret rotation, backups, and an environment-specific review.
