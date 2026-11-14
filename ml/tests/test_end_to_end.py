"""Briques du rapport de bout en bout (`ml/end_to_end.py`), qui se lance à la main."""

import numpy as np

from ml.end_to_end import FAMILIES, Couple, draw_interests, quartile_couples, schedule
from ml.simulation.spec import CONTEXT_DAYS


def test_a_rhythm_starts_after_the_context_week():
    every_three = schedule(20, 3)
    assert not every_three[:CONTEXT_DAYS].any()
    assert list(np.flatnonzero(every_three)) == [7, 10, 13, 16, 19]
    assert not schedule(20, None).any()
    assert schedule(20, 1)[CONTEXT_DAYS:].all()


def test_quartile_couples_are_picked_by_score():
    couples = [Couple([f"p{i}"], [f"h{i}"], score) for i, score in enumerate(np.linspace(0, 1, 9))]
    picked = quartile_couples(couples)
    assert [round(c.score, 3) for c in picked.values()] == [0.25, 0.5, 0.75]


def test_interests_come_mostly_from_one_family():
    known = {interest for family in FAMILIES.values() for interest in family}
    people = draw_interests(np.random.default_rng(0), 50)
    assert all(1 <= len(p) <= 4 for p in people)  # 2 à 4 tirés, moins après les doublons
    assert all(set(p) <= known for p in people)
