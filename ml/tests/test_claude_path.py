"""Claude comme générateur (issue #74), avec un faux client : aucun appel réseau.

Le modèle local est coupé (`conftest.py`) : les demandes de Claude sont alors placées à la
position qu'il annonce, sauf un test qui rallume une fausse mesure locale.
"""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from ml import claude, embedding
from ml.model import (
    InterestPair,
    generate_candidates,
    measure_message,
    provider_info,
    select_three,
    zone_for,
)
from ml.pipeline import GENERATION_SYSTEM

PAIRS = [InterestPair("gardening", "cooking"), InterestPair("jazz", "woodworking")]


def _requests(pair_count: int) -> dict[str, Any]:
    positions = [0.3, 0.5, 0.6, 0.7, 0.8, 0.9]
    return {
        "requests": [
            {
                "pair": pair,
                "format": "opinion",
                "position": position,
                "text": f"Hi Aino,\nIdea {pair}-{position}: which would you pick?\nCheers,\nMikko",
            }
            for pair in range(pair_count)
            for position in positions
        ]
    }


class FakeClaude:
    """Remplace le client `anthropic` : enregistre les appels, renvoie une réponse préparée."""

    def __init__(self, answer: Any, stop_reason: str = "end_turn", error: Exception | None = None):
        self.answer, self.stop_reason, self.error = answer, stop_reason, error
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        text = json.dumps(self.answer)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=1200, output_tokens=900),
        )


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch):
    def install(answer: Any = None, **kwargs: Any) -> FakeClaude:
        client = FakeClaude(answer if answer is not None else _requests(len(PAIRS)), **kwargs)
        monkeypatch.setattr(claude, "api_key", lambda: "test-key")
        monkeypatch.setattr(claude, "_client", lambda: client)
        return client

    return install


def test_with_a_key_claude_writes_the_requests(fake):
    client = fake()
    zone = zone_for(0.5)
    candidates = generate_candidates(PAIRS, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert provider_info().provider == "claude"
    assert candidates and all(c.provider == "claude" for c in candidates)
    assert select_three(candidates, zone, set())
    call = client.calls[0]
    assert call["model"] == claude.DEFAULT_MODEL
    assert call["system"] == GENERATION_SYSTEM
    assert call["fallbacks"] == "default"


def test_the_schema_is_strict_for_structured_outputs(fake):
    client = fake()
    generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    schema = client.calls[0]["output_config"]["format"]["schema"]
    item = schema["properties"]["requests"]["items"]
    assert schema["additionalProperties"] is False and item["additionalProperties"] is False
    assert set(item["required"]) == {"pair", "format", "position", "text"}
    assert "minimum" not in item["properties"]["pair"]


def test_the_prompt_gives_bios_and_a_target_for_every_pair(fake):
    client = fake()
    generate_candidates(
        PAIRS,
        zone_for(0.8),
        "Mikko",
        "Aino",
        avoid=[],
        seed=1,
        patient_bio="I grow tomatoes on my balcony.",
        helper_bio="Home cook, soups are my specialty.",
    )
    prompt = client.calls[0]["messages"][0]["content"]
    assert "Aino: I grow tomatoes on my balcony." in prompt
    assert "Mikko: Home cook, soups are my specialty." in prompt
    assert "0. " in prompt and "1. " in prompt and "for pair 0" not in prompt
    assert "jazz" in prompt.split("In words, for each pair:")[1]


def test_a_shared_interest_is_named_as_such_in_the_prompt(fake):
    client = fake(_requests(1))
    generate_candidates(
        [InterestPair("gardening", "Gardening")], zone_for(0.5), "Mikko", "Aino", [], seed=1
    )
    assert "gardening (shared by both)" in client.calls[0]["messages"][0]["content"]


def test_the_system_prompt_forbids_gluing_interests():
    assert "Never glue a sentence" in GENERATION_SYSTEM
    assert "Always write in English" in GENERATION_SYSTEM


@pytest.mark.parametrize(
    "setup",
    [
        {"stop_reason": "refusal"},
        {"stop_reason": "max_tokens"},
        {"answer": {"requests": []}},
    ],
)
def test_any_claude_failure_falls_back_to_the_bank(fake, setup: dict[str, Any]):
    fake(**setup)
    candidates = generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    assert candidates and all(c.provider == "offline" for c in candidates)
    assert "Claude error" in provider_info().note


def test_a_network_error_falls_back_to_the_bank(fake):
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    fake(error=anthropic.APIConnectionError(request=request))
    candidates = generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    assert all(c.provider == "offline" for c in candidates)


def test_without_any_embedding_claude_positions_are_used(fake):
    fake()
    candidates = generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    assert {c.lam for c in candidates} <= {0.3, 0.5, 0.6, 0.7, 0.8, 0.9}
    assert "estimated by Claude" in provider_info().note


def test_with_the_local_model_claude_texts_are_measured(fake, monkeypatch: pytest.MonkeyPatch):
    fake()
    calls: list[list[str]] = []

    def embed(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[1.0, float(len(text) % 7), 0.5] for text in texts]

    monkeypatch.setattr(embedding, "local_available", lambda: True)
    monkeypatch.setattr(embedding, "local_embed", embed)
    candidates = generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    assert calls and all(c.provider == "claude" for c in candidates)
    assert provider_info().note == ""


def test_claude_reviews_the_helpers_message(fake):
    client = fake({"format": "call", "safe": False, "reason": "asks for money"})
    candidate, review = measure_message("Could you lend me some cash?", PAIRS[:1])
    assert review.format == "call" and not review.safe
    assert candidate.provider == "claude"
    assert client.calls[0]["output_config"]["format"]["schema"]["additionalProperties"] is False


def test_the_cost_counter_adds_up(fake):
    fake()
    before = dict(claude.usage)
    generate_candidates(PAIRS, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    assert claude.usage["calls"] == before["calls"] + 1
    assert claude.usage["input_tokens"] == before["input_tokens"] + 1200
