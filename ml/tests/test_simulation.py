"""Les données simulées : formes, plages, reproductibilité, et sens des effets.

Ces tests vérifient que le générateur fait ce que docs/modele.md dit qu'il fait. Ils ne disent
rien sur de vrais patients.
"""

from pathlib import Path

import numpy as np
import pytest

from ml.simulation import generate, save
from ml.simulation.episodes import Moment
from ml.simulation.people import HEALTHY, PATIENT
from ml.simulation.reward import distance, reward
from ml.simulation.spec import (
    AXES,
    COMPONENTS,
    CONTEXT_DAYS,
    MODALITIES,
    SIGNALS,
    SNAPSHOT_HOURS,
    modality_indices,
)

PEOPLE, DAYS = 240, 35


@pytest.fixture(scope="module")
def data():
    return generate(n_people=PEOPLE, n_days=DAYS, healthy_share=0.4, seed=7)


def test_shapes_follow_the_spec(data):
    snapshots = DAYS * len(SNAPSHOT_HOURS)
    assert data.theta.shape == (PEOPLE, snapshots, len(SIGNALS))
    assert data.mask.shape == data.theta.shape
    assert data.state.shape == (PEOPLE, snapshots, len(COMPONENTS))
    assert data.episodes.axes.shape[1] == len(AXES)
    assert set(np.unique(data.group)) == {HEALTHY, PATIENT}


def test_the_same_seed_gives_the_same_data():
    first = generate(n_people=40, n_days=12, seed=3)
    again = generate(n_people=40, n_days=12, seed=3)
    other = generate(n_people=40, n_days=12, seed=4)
    assert np.array_equal(first.theta, again.theta, equal_nan=True)
    assert np.array_equal(first.episodes.reward, again.episodes.reward)
    assert not np.array_equal(first.theta, other.theta, equal_nan=True)


def test_every_signal_stays_within_its_plausible_range(data):
    for index, signal in enumerate(SIGNALS):
        values = data.theta[..., index][data.mask[..., index]]
        assert values.size > 0, signal.name
        assert values.min() >= signal.low, signal.name
        assert values.max() <= signal.high, signal.name


def test_missing_data_is_marked_and_realistic(data):
    assert np.array_equal(data.mask, ~np.isnan(data.theta))
    missing = 1.0 - data.mask.mean()
    assert 0.03 < missing < 0.30


def test_daily_totals_never_go_down_during_a_day(data):
    steps = data.theta[..., [s.name for s in SIGNALS].index("steps_today")]
    by_day = steps.reshape(PEOPLE, DAYS, len(SNAPSHOT_HOURS))
    complete = ~np.isnan(by_day).any(axis=2)
    assert (np.diff(by_day[complete], axis=1) >= 0).all()


def test_healthy_people_are_closer_to_the_reference_than_patients(data):
    gap = distance(data.state, data.reference_mean, data.reference_spread).mean(axis=1)
    assert gap[data.group == HEALTHY].mean() < 1.5
    assert gap[data.group == PATIENT].mean() > 2.0


def test_raw_signals_carry_the_hidden_state(data):
    """Sans lien entre θ et l'état caché, l'autoencodeur n'aurait rien à retrouver."""
    names = [s.name for s in SIGNALS]
    for signal_name, component in (("sleep_score", "sleep"), ("steps_today", "activity")):
        values = data.theta[:, 3::4, names.index(signal_name)]  # relevé de 22 h
        state = data.state[:, 3::4, COMPONENTS.index(component)]
        seen = ~np.isnan(values)
        assert np.corrcoef(values[seen], state[seen])[0, 1] > 0.4, signal_name


def test_requests_wait_for_a_full_week_of_context(data):
    log = data.episodes
    assert log.day.min() >= CONTEXT_DAYS
    assert (data.group[log.person] == PATIENT).all()
    assert ((log.axes >= 0) & (log.axes <= 1)).all()
    inside = (log.axes[:, :5] >= log.zone_low) & (log.axes[:, :5] <= log.zone_high)
    assert inside.all()
    assert (log.axes[:, 5] <= log.startup_cap).all()


def test_rewards_stay_between_0_and_100_and_are_neutral_without_change(data):
    log = data.episodes
    assert log.reward.min() >= 0 and log.reward.max() <= 100
    same = np.array([0.5, 2.0, 4.0])
    assert reward(same, same) == pytest.approx(50.0)
    assert reward(np.array([3.0]), np.array([2.0]))[0] > 50
    assert reward(np.array([3.0]), np.array([4.0]))[0] < 50


def test_a_request_that_is_too_heavy_pays_less_than_one_that_fits(data):
    log = data.episodes
    heavy, bearable = log.overload > 0.2, log.overload == 0
    assert bearable.sum() > 100 and heavy.sum() > 100
    assert log.replied[bearable].mean() > log.replied[heavy].mean() + 0.2
    assert log.reward_counterfactual[bearable].mean() > log.reward_counterfactual[heavy].mean()
    well_placed = bearable & (log.fit > 0.6)
    badly_placed = bearable & (log.fit < 0.2)
    assert (
        log.reward_counterfactual[well_placed].mean()
        > log.reward_counterfactual[badly_placed].mean()
    )


def test_a_reply_has_a_delay_and_a_length_and_silence_has_neither(data):
    log = data.episodes
    assert not np.isnan(log.delay_hours[log.replied]).any()
    assert not np.isnan(log.reply_length[log.replied]).any()
    assert np.isnan(log.delay_hours[~log.replied]).all()


def test_the_dataset_is_written_with_its_description(tmp_path: Path):
    small = generate(n_people=30, n_days=12, seed=1)
    save(small, tmp_path)
    people = np.load(tmp_path / "people.npz")
    assert people["theta"].shape == small.theta.shape
    assert set(np.load(tmp_path / "episodes.npz").files) >= {"axes", "reward", "replied"}
    assert '"signals"' in (tmp_path / "meta.json").read_text(encoding="utf-8")


def test_too_few_days_is_refused():
    with pytest.raises(ValueError):
        generate(n_people=10, n_days=CONTEXT_DAYS, seed=0)


def test_every_signal_belongs_to_one_modality():
    columns = modality_indices()
    assert set(columns) == set(MODALITIES)
    assert sorted(index for group in columns.values() for index in group) == list(
        range(len(SIGNALS))
    )
    assert [SIGNALS[index].name for index in columns["touch"]] == [
        "typing_correction_rate",
        "open_delay_minutes",
        "first_key_delay_seconds",
    ]


def test_typing_signals_get_worse_when_the_person_is_worse(data):
    """Un patient corrige plus, tarde plus à ouvrir et hésite plus : c'est écrit dans people.py."""
    names = [s.name for s in SIGNALS]
    for signal_name, component in (
        ("typing_correction_rate", "sleep"),
        ("open_delay_minutes", "engagement"),
        ("first_key_delay_seconds", "energy"),
    ):
        values = np.log(data.theta[:, 3::4, names.index(signal_name)])
        state = data.state[:, 3::4, COMPONENTS.index(component)]
        seen = ~np.isnan(values)
        assert 0.2 < seen.mean() < 0.95, signal_name  # présent certains jours seulement
        assert np.corrcoef(values[seen], state[seen])[0, 1] < -0.25, signal_name


class _FixedZones:
    """Politique de test : la même zone pour tout le monde, et elle note ce qu'on lui montre."""

    def __init__(self, cost: float) -> None:
        self.cost = cost
        self.seen_future = False
        self.feedbacks = 0

    def zones(self, moment: Moment):
        n = len(moment.slot)
        after_today = (moment.day + 1) * len(SNAPSHOT_HOURS)
        self.seen_future |= bool((~np.isnan(moment.theta[:, after_today:])).any())
        center = np.array([0.7, 0.6, self.cost, self.cost, self.cost])
        low = np.tile(center - 0.05, (n, 1))
        return low, low + 0.1, np.full(n, 0.2)

    def feedback(self, moment: Moment, axes, reaction) -> None:
        self.feedbacks += 1


def test_a_policy_chooses_the_zones_and_never_sees_the_future():
    light, heavy = _FixedZones(0.2), _FixedZones(0.9)
    gentle = generate(n_people=120, n_days=20, seed=2, policy=light)
    harsh = generate(n_people=120, n_days=20, seed=2, policy=heavy)

    assert gentle.theta.shape == (120, 20 * len(SNAPSHOT_HOURS), len(SIGNALS))
    assert not np.isnan(gentle.theta).all(axis=(0, 2)).any()  # chaque relevé a bien eu lieu
    assert not light.seen_future
    assert light.feedbacks == 20 - 1  # appelée chaque jour, sauf le dernier
    assert gentle.episodes.day.min() >= CONTEXT_DAYS
    log = gentle.episodes
    assert np.allclose(log.zone_low[:, 2], 0.15) and np.allclose(log.zone_high[:, 2], 0.25)
    assert ((log.axes[:, :5] >= log.zone_low) & (log.axes[:, :5] <= log.zone_high)).all()
    # Les mêmes personnes, des demandes trop lourdes : elles répondent bien moins.
    assert np.array_equal(gentle.group, harsh.group)
    assert log.replied.mean() > harsh.episodes.replied.mean() + 0.2
    assert log.reward_counterfactual.mean() > harsh.episodes.reward_counterfactual.mean()
