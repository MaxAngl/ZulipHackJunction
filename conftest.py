"""Réglages communs à tous les tests."""

import pytest


@pytest.fixture(autouse=True)
def offline_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les tests ne touchent jamais le réseau : Gemini est coupé, même si `.env` a une clé."""
    monkeypatch.setattr("ml.gemini.api_key", lambda: None)
