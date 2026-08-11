from __future__ import annotations

import ipaddress
from datetime import datetime
from urllib.parse import urlsplit

from farebeacon.domain.exceptions import OfferValidationError
from farebeacon.domain.money import currency_exponent
from farebeacon.domain.sources import NormalizedOffer, SearchQuery


def _timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def validate_offer(offer: NormalizedOffer, query: SearchQuery) -> None:
    if not offer.source_name.strip():
        raise OfferValidationError("source_name is required")
    if not _timezone_aware(offer.observed_at):
        raise OfferValidationError("observed_at must include a timezone")
    if offer.total_price <= 0:
        raise OfferValidationError("price must be positive")
    currency_exponent(offer.currency)
    if offer.currency.upper() != query.currency:
        raise OfferValidationError(
            "offer currency does not match query",
            details={"expected": query.currency, "received": offer.currency},
        )
    if not 0 <= offer.confidence_score <= 1:
        raise OfferValidationError("confidence_score must be between 0 and 1")
    if offer.booking_url is not None:
        _validate_booking_url(offer.booking_url)
    if not offer.segments:
        raise OfferValidationError("at least one segment is required")

    ordered = sorted(offer.segments, key=lambda segment: (segment.leg_index, segment.sequence))
    outbound = [segment for segment in ordered if segment.leg_index == 0]
    if not outbound or outbound[0].origin != query.origin:
        raise OfferValidationError("outbound origin does not match query")
    if outbound[-1].destination != query.destination:
        raise OfferValidationError("outbound destination does not match query")
    if query.max_stops is not None and len(outbound) - 1 > query.max_stops:
        raise OfferValidationError("offer exceeds max_stops")

    for index, segment in enumerate(ordered):
        if not _timezone_aware(segment.departure_at) or not _timezone_aware(segment.arrival_at):
            raise OfferValidationError("segment times must include a timezone")
        if segment.arrival_at <= segment.departure_at:
            raise OfferValidationError("segment arrival must be after departure")
        if index == 0:
            continue
        previous = ordered[index - 1]
        if segment.leg_index == previous.leg_index:
            if segment.sequence != previous.sequence + 1:
                raise OfferValidationError("segment sequence is not contiguous")
            if segment.origin != previous.destination:
                raise OfferValidationError("segments are not connected")

    if query.return_date is not None:
        inbound = [segment for segment in ordered if segment.leg_index == 1]
        if not inbound:
            raise OfferValidationError("round-trip offer has no return leg")
        if inbound[0].origin != query.destination or inbound[-1].destination != query.origin:
            raise OfferValidationError("return leg does not match query")


def _validate_booking_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise OfferValidationError("booking_url is invalid") from exc
    if parsed.scheme.lower() != "https" or hostname is None or parsed.username or parsed.password:
        raise OfferValidationError("booking_url must be an absolute HTTPS URL without credentials")
    if port not in {None, 443}:
        raise OfferValidationError("booking_url must use the default HTTPS port")
    if hostname.lower() == "localhost":
        raise OfferValidationError("booking_url cannot target a local address")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise OfferValidationError("booking_url cannot target a private or reserved address")
