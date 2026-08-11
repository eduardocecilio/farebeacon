from __future__ import annotations

import asyncio
from datetime import date

import pytest

from farebeacon.domain.exceptions import SourceExecutionError, SourceTimeoutError
from farebeacon.domain.sources import SearchQuery, SourceExecutionContext
from farebeacon.sources.mock import MockSource


def make_query() -> SearchQuery:
    return SearchQuery(
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


def make_context(**configuration: object) -> SourceExecutionContext:
    return SourceExecutionContext(
        run_id="run_test",
        source_run_id="srun_test",
        timeout_seconds=1,
        correlation_id="run_test",
        configuration=configuration,  # type: ignore[arg-type]
    )


@pytest.mark.contract
def test_mock_source_is_deterministic() -> None:
    source = MockSource()
    first = asyncio.run(source.fetch(make_query(), make_context()))
    second = asyncio.run(source.fetch(make_query(), make_context()))
    assert [item.payload for item in first.items] == [item.payload for item in second.items]
    assert len(first.items) == 2


@pytest.mark.contract
@pytest.mark.parametrize(
    ("mode", "expected_error"),
    [("error", SourceExecutionError), ("timeout", SourceTimeoutError)],
)
def test_mock_source_simulates_failures(mode: str, expected_error: type[Exception]) -> None:
    with pytest.raises(expected_error):
        asyncio.run(MockSource().fetch(make_query(), make_context(mode=mode)))


@pytest.mark.contract
def test_mock_source_simulates_empty_and_duplicate_results() -> None:
    empty = asyncio.run(MockSource().fetch(make_query(), make_context(mode="empty")))
    duplicated = asyncio.run(MockSource().fetch(make_query(), make_context(duplicate_first=True)))
    assert empty.items == ()
    assert len(duplicated.items) == 3
    assert duplicated.items[0] == duplicated.items[-1]
