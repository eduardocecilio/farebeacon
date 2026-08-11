# ADR 0002: Open source does not mean public multi-tenant SaaS

Status: accepted

## Decision

The MVP is single-tenant and self-hosted with one administrative Bearer token. The GitHub repository
may become public only after acceptance, but the service is not presented as a public account-based
product.

## Consequences

This keeps the first vertical slice useful on private infrastructure. A hosted service would require
users, resource ownership, per-user quotas, audit principals, abuse controls, privacy policy, and a
new authorization review.

