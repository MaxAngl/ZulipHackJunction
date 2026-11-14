"""Mesure de λ et profils d'intérêts par le modèle d'embeddings local (issue #69).

La plupart des tests remplacent le modèle par un faux : la CI ne télécharge rien. Les derniers
utilisent le vrai modèle, seulement s'il est déjà dans le cache Hugging Face de la machine.
"""

import hashlib
import math

import pytest

from ml import embedding
from ml.matching import InterestProfile, fallback_profile, offline_profile, stable_match
from ml.model import InterestPair, generate_candidates, measure_message, select_three, zone_for

UNKNOWN = [InterestPair("chess", "running"), InterestPair("knitting", "yoga")]


def _fake_vector(text: str) -> list[float]:
    """Un vecteur déterministe par texte, de norme 1 : de quoi donner des λ variés."""
    digest = hashlib.sha256(text.encode()).digest()
    raw = [byte - 127.5 for byte in digest[:16]]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


@pytest.fixture
def fake_local(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def embed(texts: list[str]) -> list[list[float]]:
        calls.append(list(texts))
        return [_fake_vector(text) for text in texts]

    monkeypatch.setattr(embedding, "local_available", lambda: True)
    monkeypatch.setattr(embedding, "local_embed", embed)
    return calls


def test_the_switch_turns_the_local_model_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(embedding.LOCAL_SWITCH, "off")
    assert not embedding.local_available()
    assert embedding.measure_kind("offline") == "offline"
    assert embedding.measure_kind("gemini") == "gemini"


def test_without_gemini_requests_are_measured_by_the_local_model(fake_local):
    zone = zone_for(0.5)
    candidates = generate_candidates(UNKNOWN, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert fake_local, "le modèle local n'a pas été appelé"
    assert all(c.provider == "offline" for c in candidates)  # le générateur, lui, reste la banque
    # La mesure lexicale ne donne que 0, 0,5 ou 1 pour ces intérêts inconnus de la banque.
    assert {round(c.lam, 3) for c in candidates} - {0.0, 0.5, 1.0}


def test_a_failing_local_model_falls_back_to_keywords(monkeypatch: pytest.MonkeyPatch):
    def broken(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("disque plein")

    monkeypatch.setattr(embedding, "local_available", lambda: True)
    monkeypatch.setattr(embedding, "local_embed", broken)
    pairs = [InterestPair("gardening", "cooking")]
    candidates = generate_candidates(pairs, zone_for(0.5), "Mikko", "Aino", avoid=[], seed=1)
    assert candidates
    candidate, _ = measure_message("Which herb grows best on a balcony?", pairs)
    assert not candidate.off_topic


def test_without_gemini_profiles_use_the_local_model(fake_local):
    profile = fallback_profile(["chess", "jazz"])
    assert profile.provider == f"local:{embedding.LOCAL_MODEL}"
    assert all(abs(sum(x * x for x in vector) - 1) < 1e-9 for vector in profile.vectors)


def test_mixed_profiles_are_recomputed_with_the_local_model(fake_local):
    stored_long_ago = offline_profile(["gardening"])
    new = InterestProfile(("gardening",), ((1.0,),), "gemini:old-model")
    match = stable_match({"p": stored_long_ago}, {"h": new}, {})
    assert match == {"p": "h"}
    assert ["gardening"] in fake_local


def _model_in_cache() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(embedding.LOCAL_MODEL, "config.json"), str)


real_model = pytest.mark.skipif(
    not _model_in_cache(), reason="modèle local absent du cache (jamais téléchargé ici)"
)


@pytest.fixture
def local_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(embedding.LOCAL_SWITCH, raising=False)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")  # jamais de téléchargement pendant les tests
    if not embedding.local_available():
        pytest.skip("modèle local présent mais impossible à charger")


@real_model
@pytest.mark.parametrize("theta", [0.2, 0.5, 0.8])
def test_unknown_interests_get_three_proposals_at_every_state(local_on, theta: float):
    zone = zone_for(theta)
    candidates = generate_candidates(UNKNOWN, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert len(select_three(candidates, zone, set())) == 3


@real_model
def test_the_local_measure_orders_requests_between_the_two_interests(local_on):
    pairs = [InterestPair("chess", "running")]
    about_patient, _ = measure_message("How did you first get into chess? Tell me.", pairs)
    about_helper, _ = measure_message("Two running routes: the park or the river?", pairs)
    unrelated, _ = measure_message("Could you help me move a sofa on Saturday?", pairs)
    # Côté aidant, la mesure locale se tasse un peu (0,38 ici) : on vérifie le bon côté de 0,5.
    assert about_patient.lam > 0.7 and about_helper.lam < 0.5
    assert unrelated.off_topic
