# Security policy

## Supported versions

FareBeacon is pre-1.0. Security fixes target the latest release on the default branch.

## Reporting a vulnerability

Do not open a public issue with exploit details, tokens, provider payloads, or personal information.
Use GitHub private vulnerability reporting after the repository is published.

## Boundaries

- FareBeacon stores passenger counts, not passenger identities or payment data.
- It never purchases or issues tickets.
- It does not bypass CAPTCHA, authentication, paywalls, robots controls, or provider protections.
- Browser automation, when introduced, must run in a separate worker with no direct database access.
- Source payloads are untrusted input and must be size-limited, parsed, validated, and sanitized.
- Tokens and provider secrets must be injected at runtime and removed from logs.

See [docs/security.md](docs/security.md) for the current threat model.

