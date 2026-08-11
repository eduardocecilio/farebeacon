from __future__ import annotations

import pytest
from pydantic import ValidationError

from farebeacon.config import Settings


def test_http_api_requires_an_explicit_token() -> None:
    settings = Settings(api_token=None)
    with pytest.raises(ValueError, match="FAREBEACON_API_TOKEN"):
        settings.require_api_token()


def test_placeholder_token_is_rejected_in_every_environment() -> None:
    with pytest.raises(ValidationError, match="not a placeholder"):
        Settings(api_token="change-me-use-at-least-32-random-characters")


def test_token_is_redacted_from_settings_representation() -> None:
    token = "a-valid-test-token-with-at-least-thirty-two-characters"
    settings = Settings(api_token=token)
    assert token not in repr(settings)
