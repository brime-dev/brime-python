"""Shared pytest fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.delenv("BRIME_BASE_URL", raising=False)
    # api_key explicitly passed in tests; remove env to keep tests deterministic
    monkeypatch.delenv("BRIME_API_KEY", raising=False)
