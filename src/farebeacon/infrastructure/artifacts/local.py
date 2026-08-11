from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from uuid import uuid4

from farebeacon.domain.ports.artifacts import StoredArtifact


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, *, storage_key: str, content: bytes, content_type: str) -> StoredArtifact:
        key = PurePosixPath(storage_key)
        if key.is_absolute() or ".." in key.parts or not key.parts:
            raise ValueError("unsafe artifact storage key")
        destination = self.root.joinpath(*key.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        temporary.write_bytes(content)
        temporary.replace(destination)
        return StoredArtifact(
            storage_key=key.as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            content_type=content_type,
        )
