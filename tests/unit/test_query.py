from datetime import date

import pytest

from farebeacon.domain.sources import SearchQuery


def query(**overrides: object) -> SearchQuery:
    values = {
        "origin": "bsb",
        "destination": "pvh",
        "departure_date": date(2030, 7, 10),
        "return_date": None,
        "adults": 1,
        "children": 0,
        "infants": 0,
        "cabin_class": "economy",
        "currency": "brl",
        "max_stops": 1,
    }
    values.update(overrides)
    return SearchQuery(**values)  # type: ignore[arg-type]


def test_query_normalizes_codes() -> None:
    result = query()
    assert result.origin == "BSB"
    assert result.destination == "PVH"
    assert result.currency == "BRL"


@pytest.mark.parametrize(
    "overrides",
    [
        {"origin": "BS"},
        {"destination": "BSB"},
        {"adults": 0},
        {"children": -1},
        {"max_stops": -1},
        {"return_date": date(2030, 7, 9)},
    ],
)
def test_query_rejects_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        query(**overrides)
