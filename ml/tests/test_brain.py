"""Le branchement des réseaux vers l'app : patient virtuel, zone à six axes, boucle complète.

Ces tests utilisent les poids versionnés dans `ml/weights`.
"""

import numpy as np
import pytest

from ml.model import (
    AXIS_KEYS,
    FORMATS,
    InterestPair,
    Outcome,
    VirtualPatient,
    ZoneBox,
    brain,
    generate_candidates,
    request_axes,
    select_three,
)
from ml.simulation.spec import SIGNALS, SNAPSHOT_HOURS, signal_index

PAIRS = [InterestPair("gardening", "cooking"), InterestPair("jazz", "cycling")]


def _read(level: float, seed: int = 11):
    body = VirtualPatient(seed, 0.55)
    normal = brain().normal(body.theta)
    body.set_level(level)
    return body, normal, brain().reading(body.theta, normal)


def test_a_virtual_patient_is_reproducible_and_lives_day_by_day():
    first, again, other = VirtualPatient(3), VirtualPatient(3), VirtualPatient(4)
    assert np.array_equal(first.theta, again.theta, equal_nan=True)
    assert not np.array_equal(first.theta, other.theta, equal_nan=True)
    assert first.theta.shape == (14 * len(SNAPSHOT_HOURS), len(SIGNALS))

    snapshots = len(first.theta)
    fit, overload = first.receive(np.array(request_axes(0.7, "opinion")), replied=True)
    assert len(first.theta) == snapshots + len(SNAPSHOT_HOURS)
    assert 0.0 <= fit <= 1.0 and overload >= 0.0


def test_a_helped_request_lifts_the_hidden_state_and_a_heavy_ignored_one_lowers_it():
    light = request_axes(0.7, "opinion")
    heavy = (0.1, 0.1, 0.95, 0.95, 0.95, 0.9)
    helped, ignored = VirtualPatient(5), VirtualPatient(5)
    for _ in range(5):
        helped.receive(np.array(light), replied=True)
        ignored.receive(np.array(heavy), replied=False)
    assert helped.hidden_state.mean() > ignored.hidden_state.mean() + 0.02


def test_measured_typing_replaces_the_simulated_signals():
    body = VirtualPatient(6)
    body.receive(np.array(request_axes(0.7, "opinion")), True, {"typing_correction_rate": 25.0})
    column = signal_index("typing_correction_rate")
    assert (body.theta[-len(SNAPSHOT_HOURS) :, column] == 25.0).all()


def test_the_autoencoder_reads_the_level_it_cannot_see():
    """On règle l'état caché ; les réseaux le retrouvent à partir des 25 signaux."""
    _, _, low = _read(0.25)
    _, _, high = _read(0.80)
    assert low.wellbeing < 0.40 < 0.60 < high.wellbeing
    assert brain().distance(low.state) > brain().distance(high.state)
    assert low.states.shape == (28, 6) and low.context.shape == (32,)


def test_the_learned_zone_follows_the_state():
    """Ce que l'équipe attendait, appris et non plus écrit : plus le patient va mal, plus la
    demande se rapproche de ses intérêts, et plus elle doit être légère."""
    low = brain().zone(_read(0.25)[2])
    high = brain().zone(_read(0.80)[2])
    assert low.center > high.center + 0.1
    assert low.effort_max < high.effort_max
    for zone in (low, high):
        assert zone.box is not None
        assert 0.0 <= zone.low < zone.high <= 1.0
        assert zone.center == pytest.approx(zone.common_center)  # sans vecteur : modèle général

    allowed_low = [key for key, fmt in FORMATS.items() if low.box.allows_costs(fmt.axes)]
    allowed_high = [key for key, fmt in FORMATS.items() if high.box.allows_costs(fmt.axes)]
    assert "opinion" in allowed_low and "call" not in allowed_low
    assert set(allowed_low) < set(allowed_high)


def test_a_zone_box_never_lets_a_cost_through_and_never_demands_one():
    box = ZoneBox(low=(0.6, 0.6, 0.3, 0.3, 0.3), high=(0.8, 0.8, 0.5, 0.5, 0.5), startup_max=0.2)
    fine = (0.7, 0.7, 0.4, 0.4, 0.4, 0.1)
    assert box.allows(fine) and box.shortfall(fine) == 0.0
    assert not box.allows((0.7, 0.7, 0.6, 0.4, 0.4, 0.1))  # trop long : la sécurité joue
    assert not box.allows((0.7, 0.7, 0.4, 0.4, 0.4, 0.3))  # trop coûteux à démarrer
    assert not box.allows((0.3, 0.7, 0.4, 0.4, 0.4, 0.1))  # mal placé entre les intérêts
    lighter = (0.7, 0.2, 0.1, 0.1, 0.1, 0.0)
    assert box.allows(lighter)  # plus léger et plus abstrait que visé : permis
    assert box.shortfall(lighter) > 0.0  # mais moins bien classé


def test_requests_carry_six_positions_and_the_selection_respects_the_box():
    zone = brain().zone(_read(0.55)[2])
    candidates = generate_candidates(PAIRS, zone, "Mikko", "Aino", avoid=[], seed=1)
    assert all(candidate.axes is not None and len(candidate.axes) == 6 for candidate in candidates)
    assert len(AXIS_KEYS) == 6
    chosen = select_three(candidates, zone, set())
    assert 1 <= len(chosen) <= 3
    for _, candidate in chosen:
        assert zone.box is not None and zone.box.allows(candidate.axes)


def test_reward_and_personal_vector_close_the_loop():
    body, normal, before = _read(0.5)
    zone = brain().zone(before)
    axes = request_axes(zone.center, "opinion")
    body.receive(np.array(axes), replied=True)
    after = brain().reading(body.theta, normal)
    reward = brain().reward(before, after)
    assert 0.0 <= reward <= 100.0
    assert brain().reward(before, before) == pytest.approx(50.0)

    nothing = brain().learn([])
    assert nothing.shape == (8,) and not nothing.any()
    vector = brain().learn([Outcome(before.context, axes, reward, True)] * 6)
    assert vector.shape == (8,) and np.abs(vector).max() > 0.0
    personal = brain().zone(after, vector)
    assert personal.box is not None and personal.common_center == brain().zone(after).center
