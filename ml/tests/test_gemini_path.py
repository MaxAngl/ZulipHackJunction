"""Le chemin Gemini, exercé avec une fausse API : aucun appel réseau.

Ces tests ne prouvent pas que la vraie API répond comme attendu (pour cela :
`uv run python -m ml.check_gemini`). Ils vérifient que notre code construit les requêtes,
lit les réponses, écarte ce qui est invalide et bascule hors ligne en cas d'erreur.
"""

import json
from typing import Any

import pytest

from ml import embedding, gemini, lexicon
from ml.model import (
    InterestPair,
    Zone,
    ZoneBox,
    generate_candidates,
    measure_message,
    provider_info,
    zone_for,
)

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
        self.embeddings_down = False

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, body))
        if self.down:
            raise gemini.GeminiError(503, "indisponible")
        if path.endswith(":batchEmbedContents"):
            if self.embeddings_down:
                raise gemini.GeminiError(429, "quota du jour épuisé")
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
    monkeypatch.setattr("ml.gemini.time.sleep", lambda _seconds: None)  # pas d'attente réelle
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


def test_with_a_six_axis_zone_the_prompt_names_the_formats_that_suit(fake: FakeGemini):
    """Un format léger peut être exclu alors qu'un plus lourd passe : on nomme les formats."""
    # Exposition personnelle plafonnée à 0,30 : « memory » (0,45) est exclu, « explain » passe.
    box = ZoneBox(low=(0.6, 0.6, 0.2, 0.2, 0.1), high=(0.8, 0.8, 0.5, 0.5, 0.3), startup_max=0.15)
    zone = Zone(center=0.7, half_width=0.1, effort_max=0.5, common_center=0.7, box=box)
    generate_candidates(PAIRS, zone, "Mikko", "Aino", avoid=[], seed=1)
    prompt = fake.calls[0][1]["contents"][0]["parts"][0]["text"]
    assert "Formats that suit this recipient right now: opinion, explain, review." in prompt
    assert "Effort ceiling" not in prompt
    assert "0.60 to 0.80" in prompt


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


def _busy_then_fine(monkeypatch: pytest.MonkeyPatch, failures: int) -> list[str]:
    """Remplace l'appel réseau : `failures` réponses 503, puis des embeddings normaux."""
    calls: list[str] = []

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        calls.append(path)
        if len(calls) <= failures:
            raise gemini.GeminiError(503, "busy")
        return {"embeddings": [{"values": [1.0, 0.0]} for _ in body["requests"]]}

    monkeypatch.setattr("ml.gemini.api_key", lambda: "test-key")
    monkeypatch.setattr("ml.gemini._post", post)
    monkeypatch.setattr("ml.gemini.time.sleep", lambda _seconds: None)
    return calls


def test_an_overloaded_embedding_call_is_retried(monkeypatch: pytest.MonkeyPatch):
    """Vu en réel : Gemini répond 503 quand il est surchargé, puis répond normalement.

    Pour les embeddings, on réessaie au lieu de changer de modèle : un autre modèle changerait
    l'échelle de la mesure de position.
    """
    calls = _busy_then_fine(monkeypatch, failures=1)
    assert gemini.embed(["gardening", "cooking"]) == [[1.0, 0.0], [1.0, 0.0]]
    assert len(calls) == 2


def test_a_lasting_overload_ends_in_an_error_after_three_tries(monkeypatch: pytest.MonkeyPatch):
    calls = _busy_then_fine(monkeypatch, failures=10)
    with pytest.raises(gemini.GeminiError) as caught:
        gemini.embed(["gardening"])
    assert caught.value.status == 503
    assert len(calls) == 3


def test_a_generated_request_reads_like_a_normal_message():
    """Vu en réel : le modèle léger oublie parfois la majuscule et la ponctuation finale."""
    from ml.pipeline import _tidy

    assert _tidy("could you explain how you grow basil indoors") == (
        "Could you explain how you grow basil indoors?"
    )
    assert _tidy("  tell me about  your first garden ") == "Tell me about your first garden."
    assert (
        _tidy("Which herb goes best with tomato soup?") == "Which herb goes best with tomato soup?"
    )
    assert _tidy("") == ""


def test_a_greeting_and_a_signature_keep_their_own_lines():
    """Bonjour, demande, fin, signature : chaque ligne reste, la signature sans point final."""
    from ml.pipeline import _tidy

    assert _tidy("hi Aino,\n could you share  a basil tip?\n\nthanks a lot,\nMikko") == (
        "Hi Aino,\nCould you share a basil tip?\nThanks a lot,\nMikko"
    )
    assert _tidy("Thanks,\nIn&egrave;s") == "Thanks,\nInès"  # vu en réel le 14/11


def test_without_embeddings_the_gemini_texts_keep_the_position_gemini_aimed_at(
    fake: FakeGemini,
):
    """Quota d'embeddings épuisé : les demandes de Gemini restent, à la position visée."""
    fake.embeddings_down = True
    candidates = _generate()
    aimed = {item["text"]: item.get("position") for item in GENERATED["requests"]}
    assert candidates and {candidate.text for candidate in candidates} <= set(aimed)
    for candidate in candidates:
        if aimed[candidate.text] is None:
            assert candidate.provider == "offline"  # sans position visée : mesure par mots-clés
        else:
            assert candidate.lam == pytest.approx(aimed[candidate.text])
            assert not candidate.off_topic
    assert "estimated by Gemini" in provider_info().note


def test_offline_requests_greet_by_name_and_vary_their_words():
    """Hors ligne aussi : le prénom du patient, la signature de l'aidant, des formules variées."""
    candidates = generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    lines = [candidate.text.splitlines() for candidate in candidates]
    assert all(len(parts) == 4 for parts in lines)
    assert all("Aino" in parts[0] and parts[3] == "Mikko" for parts in lines)
    assert len({parts[0] for parts in lines}) >= 5  # pas toujours la même formule d'appel
    assert len({parts[2] for parts in lines}) >= 5  # ni la même formule de fin

    # Une seconde génération ne reprend pas les mêmes demandes, quel que soit l'habillage.
    again = generate_candidates(
        PAIRS, zone_for(0.5), "Mikko", "Aino", [c.text for c in candidates], seed=2
    )
    assert not {c.text.splitlines()[1] for c in again} & {parts[1] for parts in lines}
