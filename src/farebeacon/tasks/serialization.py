from __future__ import annotations

from datetime import date, datetime
from typing import Any

from farebeacon.domain.sources import RawSourceItem, SearchQuery, SourceBatch


def serialize_query(query: SearchQuery) -> dict[str, Any]:
    return {
        "origin": query.origin,
        "destination": query.destination,
        "departure_date": query.departure_date.isoformat(),
        "return_date": query.return_date.isoformat() if query.return_date else None,
        "adults": query.adults,
        "children": query.children,
        "infants": query.infants,
        "cabin_class": query.cabin_class,
        "currency": query.currency,
        "max_stops": query.max_stops,
        "locale": query.locale,
        "market": query.market,
    }


def deserialize_query(payload: dict[str, Any]) -> SearchQuery:
    return SearchQuery(
        origin=str(payload["origin"]),
        destination=str(payload["destination"]),
        departure_date=date.fromisoformat(str(payload["departure_date"])),
        return_date=date.fromisoformat(str(payload["return_date"]))
        if payload.get("return_date")
        else None,
        adults=int(payload["adults"]),
        children=int(payload["children"]),
        infants=int(payload["infants"]),
        cabin_class=str(payload["cabin_class"]),
        currency=str(payload["currency"]),
        max_stops=int(payload["max_stops"]) if payload.get("max_stops") is not None else None,
        locale=str(payload["locale"]),
        market=str(payload["market"]),
    )


def serialize_batch(batch: SourceBatch) -> dict[str, Any]:
    return {
        "source_name": batch.source_name,
        "query": serialize_query(batch.query),
        "observed_at": batch.observed_at.isoformat(),
        "items": [
            {"source_offer_id": item.source_offer_id, "payload": item.payload}
            for item in batch.items
        ],
        "quota_cost": batch.quota_cost,
        "http_status": batch.http_status,
        "parser_version": batch.parser_version,
    }


def deserialize_batch(payload: dict[str, Any]) -> SourceBatch:
    return SourceBatch(
        source_name=str(payload["source_name"]),
        query=deserialize_query(payload["query"]),
        observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        items=tuple(
            RawSourceItem(
                source_offer_id=item.get("source_offer_id"),
                payload=dict(item["payload"]),
            )
            for item in payload["items"]
        ),
        quota_cost=int(payload.get("quota_cost", 0)),
        http_status=int(payload["http_status"]) if payload.get("http_status") else None,
        parser_version=payload.get("parser_version"),
    )
