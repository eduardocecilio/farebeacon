# Security design

## Current threat model

FareBeacon accepts authenticated monitor commands and untrusted source payloads. Relevant threats
include credential leakage, duplicate commands, parser abuse, malicious URLs, oversized artifacts,
task replay, lateral container movement, and accidental database exposure.

## Implemented controls

- constant-time comparison of the single high-entropy MVP token;
- no token in query parameters, responses, or application logs;
- strict Pydantic request schemas and structured error responses;
- scoped idempotency records with request hashes;
- PostgreSQL and Redis have no host port mapping;
- API and workers run non-root with all Linux capabilities dropped;
- read-only application root filesystems with bounded tmpfs;
- separate source and normalization queues;
- generated, traversal-safe artifact keys and content hashes;
- no Docker socket, browser, payment data, passenger identity, or arbitrary execution;
- response headers denying framing and browser capabilities.

## Known MVP limits

- one administrative token means no user-level authorization or audit principal;
- local artifacts have no encryption or retention cleanup yet;
- the static IATA syntax check is not a complete licensed airport/metro-code catalogue;
- Compose resource limits depend on the Docker runtime honoring `deploy.resources`;
- network egress allowlists arrive with the first real source.

Never expose this alpha directly to the public internet without a reverse proxy, TLS, rate limiting,
secret rotation, backups, and an environment-specific review.

