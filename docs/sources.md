# Source development

Each installed source is a `SearchSource` paired with a `SourceParser` in `SourceRegistry`.

```text
SearchSource.fetch(query, context) -> SourceBatch[RawSourceItem]
SourceParser.normalize(raw item)   -> NormalizedOffer[]
```

A source may perform network acquisition but cannot import repositories or write offers. The parser
knows the provider payload; downstream validation and persistence know only normalized domain types.

## Required proposal information

Before adding a real provider, document:

- official API or page being accessed;
- terms of use and data-license compatibility;
- authentication and secret scope;
- rate and concurrency limits;
- estimated and actual quota costs;
- permitted cache lifetime;
- parser fixtures and contract-change detection;
- timeout, retry, and error classification;
- whether returned links are stable and user-verifiable.

Do not guess an external contract. Capture allowed fixtures from an official sandbox or documented
API and remove credentials and personal data.

## MockSource modes

Both `mock` and `mock-secondary` are offline test adapters. Source configuration supports:

- `mode: success` (default)
- `mode: empty`
- `mode: error`
- `mode: timeout`
- `base_price_minor: <integer>`
- `duplicate_first: true`

`mock-secondary` exists to exercise cross-source correlation and partial failure without pretending
to be a real supplier.

## Browser sources

Browser automation is intentionally absent. When introduced, Playwright belongs only in a separate
image and queue. The browser worker must have no direct database credentials, arbitrary URL input,
downloads, private-network reachability, or access-control bypass behavior.

