"""Réglages communs à tous les tests."""

import os

import pytest

# La vraie app écrit dans une base en mémoire pendant les tests, jamais dans data/needed.db.
os.environ["NEEDED_DB"] = ":memory:"


@pytest.fixture(autouse=True)
def offline_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les tests ne touchent jamais le réseau : Gemini est coupé, même si `.env` a une clé."""
    monkeypatch.setattr("ml.gemini.api_key", lambda: None)
