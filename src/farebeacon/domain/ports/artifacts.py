from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    storage_key: str
    sha256: str
    size_bytes: int
    content_type: str


class ArtifactStore(Protocol):
    def put(self, *, storage_key: str, content: bytes, content_type: str) -> StoredArtifact: ...
