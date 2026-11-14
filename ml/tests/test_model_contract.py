"""Contrat ml/ -> backend/ : ce que le backend attend de `ml.model`."""

import pytest

from ml.formats import FORMATS
from ml.model import (
    InterestPair,
    ZoneParams,
    generate_candidates,
    learn,
    measure_message,
    provider_info,
    select_three,
    zone_for,
)

PAIRS = [InterestPair("gardening", "cooking"), InterestPair("jazz", "cycling")]


def _generate(theta: float = 0.5):
    zone = zone_for(theta)
    return zone, generate_candidates(PAIRS, zone, "Mikko", "Aino", avoid=[], seed=1)


def test_zone_follows_the_starting_rule():
    low_state, high_state = zone_for(0.2), zone_for(0.9)
    assert low_state.center > high_state.center  # plus mal = plus près des intérêts du patient
    assert low_state.effort_max < high_state.effort_max  # plus mal = demande plus légère
    for zone in (low_state, high_state):
        assert 0.0 <= zone.low <= zone.center <= zone.high <= 1.0
        assert zone.contains(zone.center, 0.0)
        assert not zone.contains(zone.center, 1.0)


def test_a_new_patient_gets_the_common_zone():
    zone = zone_for(0.5)
    assert zone.center == pytest.approx(zone.common_center)


def test_learning_moves_and_narrows_the_zone():
    start = ZoneParams()
    center = zone_for(0.5, start).center
    better = learn(start, theta=0.5, lam_sent=center - 0.1, reward=0.10)
    worse = learn(start, theta=0.5, lam_sent=center - 0.1, reward=-0.04)
    assert zone_for(0.5, better).center < center  # la demande a marché : on s'en rapproche
    assert zone_for(0.5, worse).center > center  # elle a échoué : on s'en éloigne
    assert better.n_obs == 1
    assert zone_for(0.5, better).half_width < zone_for(0.5, start).half_width


def test_generated_candidates_are_measured():
    _, candidates = _generate()
    assert len(candidates) >= 6
    assert len({candidate.text for candidate in candidates}) == len(candidates)
    for candidate in candidates:
        assert 0.0 <= candidate.lam <= 1.0
        assert candidate.format in FORMATS
        assert candidate.effort == FORMATS[candidate.format].effort
        assert candidate.provider == "offline"


def test_the_three_proposals_are_inside_the_zone_and_distinct():
    zone, candidates = _generate()
    chosen = select_three(candidates, zone, tried_formats=set())
    assert 1 <= len(chosen) <= 3
    assert len({slot for slot, _ in chosen}) == len(chosen)
    assert len({candidate.id for _, candidate in chosen}) == len(chosen)
    assert all(zone.contains(candidate.lam, candidate.effort) for _, candidate in chosen)


def test_a_message_is_placed_between_the_two_interests():
    on_patient, _ = measure_message("Which herb should I grow on my balcony?", PAIRS)
    on_helper, _ = measure_message("Soup or pasta for my dinner menu?", PAIRS)
    unrelated, _ = measure_message("What do you think of this spreadsheet?", PAIRS)
    assert on_patient.lam >= 0.9
    assert on_helper.lam <= 0.1
    assert unrelated.off_topic
    assert unrelated.lam == 0.0


def test_a_written_message_gets_a_format_and_a_safety_check():
    _, review = measure_message("Could we have a short call about your garden?", PAIRS)
    assert review.format == "call"
    assert review.safe
    _, unsafe = measure_message("Can you lend me money for seeds?", PAIRS)
    assert not unsafe.safe


def test_without_a_key_the_generator_is_offline():
    info = provider_info()
    assert info.provider == "offline"
    assert info.model is None
