from dataclasses import replace
from datetime import date

import pytest

from farebeacon.domain.exceptions import OfferValidationError
from farebeacon.domain.sources import SearchQuery, SourceExecutionContext
from farebeacon.domain.validation import validate_offer
from farebeacon.sources.mock import MockSource, MockSourceParser


def test_mock_offer_passes_domain_validation() -> None:
    query = SearchQuery(
        origin="BSB",
        destination="PVH",
        departure_date=date(2030, 7, 10),
        return_date=None,
        adults=1,
        children=0,
        infants=0,
        cabin_class="economy",
        currency="BRL",
        max_stops=1,
    )
    context = SourceExecutionContext(
        run_id="run_test",
        source_run_id="srun_test",
        timeout_seconds=1,
        correlation_id="run_test",
    )
    import asyncio

    batch = asyncio.run(MockSource().fetch(query, context))
    parsed = MockSourceParser().normalize(
        batch.items[0],
        query=query,
        observed_at=batch.observed_at,
    )[0]
    validate_offer(parsed, query)


def test_validation_rejects_offer_over_stop_limit() -> None:
    query = SearchQuery(
        origin="BSB",
        destination="PVH",
        departure_date=date(2030, 7, 10),
        return_date=None,
        adults=1,
        children=0,
        infants=0,
        cabin_class="economy",
        currency="BRL",
        max_stops=0,
    )
    context = SourceExecutionContext(
        run_id="run_test",
        source_run_id="srun_test",
        timeout_seconds=1,
        correlation_id="run_test",
    )
    import asyncio

    connected_query = replace(query, max_stops=1)
    batch = asyncio.run(MockSource().fetch(connected_query, context))
    parsed = MockSourceParser().normalize(
        batch.items[1],
        query=connected_query,
        observed_at=batch.observed_at,
    )[0]
    with pytest.raises(OfferValidationError):
        validate_offer(parsed, query)
