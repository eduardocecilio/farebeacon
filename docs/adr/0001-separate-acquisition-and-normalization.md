# ADR 0001: Separate acquisition from normalization

Status: accepted

## Context

The original draft made `SearchSource.search()` return `NormalizedOffer` while also requiring a raw
result, a provider parser, and a separate normalization queue. Those contracts cannot all be true.

## Decision

`SearchSource.fetch()` returns a `SourceBatch` of provider-shaped `RawSourceItem` values. A registered
`SourceParser` converts each item to normalized domain offers in the `normalize` queue.

## Consequences

- acquisition workers cannot persist domain entities;
- parser changes can be versioned and tested against fixtures;
- browser workers can eventually pass artifact references without database credentials;
- raw payload transport must remain size-bounded; real large payloads will use artifact references.

