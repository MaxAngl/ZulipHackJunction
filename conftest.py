"""Réglages communs à tous les tests."""

import os

import pytest

# La vraie app écrit dans une base en mémoire pendant les tests, jamais dans data/needed.db.
os.environ["NEEDED_DB"] = ":memory:"


@pytest.fixture(autouse=True)
def offline_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les tests ne touchent jamais le réseau : Gemini et Claude sont coupés, même si `.env` a
    une clé.

    Le modèle d'embeddings local aussi : la CI ne le télécharge pas, et les tests gardent la
    mesure lexicale. `ml/tests/test_local_embeddings.py` le rallume quand il est en cache.
    """
    monkeypatch.setattr("ml.gemini.api_key", lambda: None)
    monkeypatch.setattr("ml.claude.api_key", lambda: None)
    monkeypatch.setenv("NEEDED_LOCAL_EMBEDDINGS", "off")
