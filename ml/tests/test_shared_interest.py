"""Joker (issue #71) : un intérêt commun place la demande au centre de la zone du patient.

Sans le joker, λ vaut 0,5 pour tout texte quand le patient et l'aidant ont le même intérêt, et
seule la zone d'un patient grave contient 0,5. Les tests tournent sur la mesure par mots-clés
(`conftest.py`) ; le dernier vérifie le seuil de ressemblance avec le vrai modèle local.
"""

import pytest

from ml import embedding
from ml.model import InterestPair, generate_candidates, measure_message, select_three, zone_for
from ml.pipeline import SHARED_SIMILARITY, _shared

SAME = [InterestPair("gardening", "gardening")]
# Zone d'un patient presque guéri (0,70 à 1) et d'un patient moyen : 0,5 n'y entre pas.
STATES = [0.2, 0.5]


@pytest.mark.parametrize("theta", STATES)
def test_a_shared_interest_gets_proposals_at_every_state(theta: float):
    zone = zone_for(theta)
    assert not zone.low <= 0.5 <= zone.high  # sans joker, rien ne passerait
    candidates = generate_candidates(SAME, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert {c.lam for c in candidates if not c.off_topic} == {round(zone.center, 3)}
    assert select_three(candidates, zone, set())


def test_the_name_is_compared_without_case_or_spaces():
    pairs = [InterestPair("Board  Games", "board games")]
    zone = zone_for(0.2)
    candidates = generate_candidates(pairs, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert all(c.lam == round(zone.center, 3) for c in candidates if not c.off_topic)


def test_different_interests_keep_their_measured_position():
    pairs = [InterestPair("gardening", "cooking")]
    zone = zone_for(0.2)
    candidates = generate_candidates(pairs, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert len({c.lam for c in candidates}) > 2


def test_a_message_on_a_shared_interest_takes_the_zone_center():
    zone = zone_for(0.2)
    written, _ = measure_message("Could you show me your tomato plants?", SAME, zone=zone)
    assert written.lam == round(zone.center, 3) and not written.off_topic
    without_zone, _ = measure_message("Could you show me your tomato plants?", SAME)
    assert without_zone.lam == 0.5


def test_an_unrelated_message_stays_off_topic_even_on_a_shared_interest():
    unrelated, _ = measure_message(
        "What do you think of this spreadsheet?", SAME, zone=zone_for(0.2)
    )
    assert unrelated.off_topic


def test_the_threshold_is_a_similarity():
    pair = InterestPair("gardening", "garden")
    assert _shared(pair, [1.0, 0.0], [0.9, 0.1], "local")  # cos 0,99
    assert not _shared(pair, [1.0, 0.0], [0.6, 0.8], "local")  # cos 0,6
    assert SHARED_SIMILARITY["local"] == 0.85


def _model_in_cache() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(embedding.LOCAL_MODEL, "config.json"), str)


@pytest.mark.skipif(not _model_in_cache(), reason="modèle local absent du cache")
def test_with_the_local_model_synonyms_are_shared_and_neighbours_are_not(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(embedding.LOCAL_SWITCH, raising=False)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    if not embedding.local_available():
        pytest.skip("modèle local impossible à charger")

    def shared(patient: str, helper: str) -> bool:
        p, h = embedding.local_embed([patient, helper])
        return _shared(InterestPair(patient, helper), p, h, "local")

    assert shared("gardening", "jardinage")
    assert shared("photography", "photo")
    assert not shared("knitting", "sewing")
    assert not shared("baking", "cooking")
