# Contributing

Thank you for helping improve FareBeacon.

1. Open an issue before introducing a real source or changing a public API contract.
2. Keep acquisition, parsing, normalization, persistence, and notifications separate.
3. Add unit and contract fixtures without live network dependencies.
4. Run `make check` before proposing a change.
5. Never commit provider credentials, raw personal data, browser profiles, or live artifacts.

When `pyproject.toml` or `requirements-build.in` dependencies change, run `make lock` and commit all
three hash-pinned lockfiles.
The command runs pip-tools in the pinned Python container; it does not install tooling on the host.

Real source proposals must document provider terms, rate limits, data licensing, cache rules, quota
cost, and failure behavior. Implementations that evade access controls will not be accepted.
