from __future__ import annotations

from typing import Any


class DomainError(Exception):
    code = "DOMAIN_ERROR"


class OfferValidationError(DomainError):
    code = "INVALID_OFFER"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class SourceExecutionError(DomainError):
    code = "SOURCE_TEMPORARILY_UNAVAILABLE"
    retryable = True


class SourceTimeoutError(SourceExecutionError):
    code = "SOURCE_TIMEOUT"


class SourceContractError(DomainError):
    code = "SOURCE_CONTRACT_CHANGED"
    retryable = False
