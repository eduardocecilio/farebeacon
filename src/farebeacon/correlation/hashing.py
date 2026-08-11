from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC

from farebeacon.domain.sources import NormalizedOffer

HASH_VERSION = "v1"


def _canonical_code(value: str | None) -> str | None:
    return re.sub(r"[^A-Z0-9]", "", value.upper()) if value else None


def itinerary_hash(offer: NormalizedOffer) -> str:
    segments = []
    for segment in sorted(offer.segments, key=lambda item: (item.leg_index, item.sequence)):
        segments.append(
            {
                "leg": segment.leg_index,
                "sequence": segment.sequence,
                "origin": segment.origin.upper(),
                "destination": segment.destination.upper(),
                "departure_at": segment.departure_at.astimezone(UTC).isoformat(timespec="seconds"),
                "arrival_at": segment.arrival_at.astimezone(UTC).isoformat(timespec="seconds"),
                "marketing_airline": _canonical_code(segment.marketing_airline),
                "operating_airline": _canonical_code(segment.operating_airline),
                "flight_number": _canonical_code(segment.flight_number),
            }
        )
    payload = json.dumps(
        {"version": HASH_VERSION, "segments": segments},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{HASH_VERSION}:{hashlib.sha256(payload.encode()).hexdigest()}"


def quote_fingerprint(offer: NormalizedOffer, itinerary_digest: str) -> str:
    payload = {
        "itinerary": itinerary_digest,
        "source": offer.source_name.lower(),
        "source_offer_id": offer.source_offer_id,
        "fare_brand": offer.fare_brand,
        "baggage_summary": offer.baggage_summary,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()
