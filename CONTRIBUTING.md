# Contributing

Thank you for helping improve FareBeacon.

1. Open an issue before introducing a real source or changing a public API contract.
2. Keep acquisition, parsing, normalization, persistence, and notifications separate.
3. Add unit and contract fixtures without live network dependencies.
4. Run `make lint` and `make test` before proposing a change.
5. Never commit provider credentials, raw personal data, browser profiles, or live artifacts.

Real source proposals must document provider terms, rate limits, data licensing, cache rules, quota
cost, and failure behavior. Implementations that evade access controls will not be accepted.

