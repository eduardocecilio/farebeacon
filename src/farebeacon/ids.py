from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str) -> str:
    """Return an opaque, sortable-safe-enough public identifier.

    UUID randomness makes retries safe when paired with database uniqueness. Prefixes keep logs and
    API payloads readable without leaking database implementation details.
    """

    return f"{prefix}_{uuid4().hex}"
