"""Le chemin Gemini, exercé avec une fausse API : aucun appel réseau.

Ces tests ne prouvent pas que la vraie API répond comme attendu (pour cela :
`uv run python -m ml.check_gemini`). Ils vérifient que notre code construit les requêtes,
lit les réponses, écarte ce qui est invalide et bascule hors ligne en cas d'erreur.
"""

import json
from typing import Any

import pytest

from ml import embedding, gemini, lexicon
from ml.model import InterestPair, generate_candidates, measure_message, provider_info, zone_for

PAIRS = [InterestPair("gardening", "cooking"), InterestPair("jazz", "cycling")]
DIMS = sorted(lexicon.all_interests())

GENERATED = {
    "requests": [
        {
            "pair": 0,
            "format": "opinion",
            "position": 0.7,
            "text": "Which herb from your garden goes best with a tomato soup?",
        },
        {
            "pair": 1,
            "format": "call",
            "position": 0.2,
            "text": "Could we have a call about my bike route?",
        },
        {
            "pair": 0,
            "format": "unknown",
            "position": 1.0,
            "text": "Could you explain how to grow a herb garden?",
        },
        {
            "pair": 0,
            "format": "opinion",
            "position": 0.4,
            "text": "I'm cooking a dinner menu tonight. Which plant should I grow next?",
        },
        {"pair": 7, "format": "opinion", "text": "This one names a pair that does not exist."},
        {"pair": 0, "format": "opinion", "text": ""},
    ]
}


def _fake_vector(text: str) -> list[float]:
    # Comme de vrais embeddings : tous les textes se ressemblent un peu (le 0,3 commun).
    return [0.3 + value for value in embedding.lexical_vector(text, DIMS)]


def _text_response(payload: Any) -> dict[str, Any]:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


class FakeGemini:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.refuse_schema = False
        self.down = False

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, body))
        if self.down:
            raise gemini.GeminiError(503, "indisponible")
        if path.endswith(":batchEmbedContents"):
            texts = [request["content"]["parts"][0]["text"] for request in body["requests"]]
            return {"embeddings": [{"values": _fake_vector(text)} for text in texts]}
        if self.refuse_schema and "responseJsonSchema" in body["generationConfig"]:
            raise gemini.GeminiError(400, "champ inconnu")
        system = body["systemInstruction"]["parts"][0]["text"]
        if system.startswith("You review"):
            return _text_response({"format": "explain", "safe": True, "reason": ""})
        return _text_response(GENERATED)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeGemini:
    api = FakeGemini()
    monkeypatch.setattr("ml.gemini.api_key", lambda: "test-key")
    monkeypatch.setattr("ml.gemini._post", api.post)
    monkeypatch.setattr("ml.embedding._gemini_cache", {})
    monkeypatch.setattr("ml.pipeline._scale", {"gain": 1.0, "shift": 0.0})
    return api


def _generate():
    return generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)


def test_gemini_requests_are_parsed_measured_and_cleaned(fake: FakeGemini):
    candidates = _generate()
    assert [candidate.provider for candidate in candidates] == ["gemini"] * 4
    assert provider_info().provider == "gemini"

    bridge, on_helper, on_patient, mostly_helper = candidates
    assert on_patient.format == "explain"  # format inconnu : reconnu d'après le texte
    # L'ordre mesuré suit le contenu des textes, de l'aidant vers le patient.
    assert on_helper.lam < mostly_helper.lam < bridge.lam < on_patient.lam
    # L'échelle est recalée sur le lot : chaque mesure reste proche de ce qui était visé.
    for candidate in candidates:
        assert candidate.intended is not None
        assert abs(candidate.lam - candidate.intended) < 0.25


def test_the_prompt_carries_the_zone(fake: FakeGemini):
    zone = zone_for(0.5)
    _generate()
    path, body = fake.calls[0]
    prompt = body["contents"][0]["parts"][0]["text"]
    assert path.endswith(":generateContent")
    assert f"{zone.low:.2f} to {zone.high:.2f}" in prompt
    assert f"Effort ceiling: {zone.effort_max:.2f}" in prompt
    assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_a_refused_configuration_is_retried_more_simply(fake: FakeGemini):
    fake.refuse_schema = True
    candidates = _generate()
    generate_calls = [path for path, _ in fake.calls if path.endswith(":generateContent")]
    assert len(generate_calls) == 3  # deux refus, puis la requête sans schéma passe
    assert candidates and candidates[0].provider == "gemini"


def test_when_gemini_is_down_the_offline_bank_takes_over(fake: FakeGemini):
    fake.down = True
    candidates = _generate()
    assert candidates
    assert all(candidate.provider == "offline" for candidate in candidates)
    assert "503" in provider_info().note


def test_a_written_message_is_reviewed_and_measured_with_gemini(fake: FakeGemini):
    measured, review = measure_message("How do I grow a herb garden for my soup?", PAIRS)
    assert review.format == "explain"
    assert review.safe
    assert measured.provider == "gemini"
    assert measured.pair == PAIRS[0]
    assert 0.5 < measured.lam < 1.0
