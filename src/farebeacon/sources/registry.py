from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from farebeacon.domain.sources import SearchSource, SourceParser
from farebeacon.sources.mock.parser import MockSourceParser
from farebeacon.sources.mock.source import MockSource


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    source: SearchSource
    parser: SourceParser


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, RegisteredSource] = {}

    def register(self, source: SearchSource, parser: SourceParser) -> None:
        if source.name != parser.source_name:
            raise ValueError("source and parser names must match")
        if source.name in self._sources:
            raise ValueError(f"source already registered: {source.name}")
        self._sources[source.name] = RegisteredSource(source=source, parser=parser)

    def get(self, name: str) -> RegisteredSource:
        try:
            return self._sources[name]
        except KeyError as exc:
            raise KeyError(f"source not registered: {name}") from exc

    def list(self) -> tuple[RegisteredSource, ...]:
        return tuple(self._sources[name] for name in sorted(self._sources))


@lru_cache(maxsize=1)
def get_source_registry() -> SourceRegistry:
    registry = SourceRegistry()
    for name in ("mock", "mock-secondary"):
        registry.register(MockSource(name=name), MockSourceParser(source_name=name))
    return registry
