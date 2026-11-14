"""Les réseaux : formes, garde-fous de la zone, ajout d'une modalité, entraînement de bout en bout.

Ces tests vérifient la machinerie. Ils ne disent rien de la qualité des réseaux, qui se mesure
avec `ml.nets.evaluate` sur un vrai jeu simulé.
"""

from pathlib import Path

import numpy as np
import pytest
import torch

from ml.nets.features import CONTEXT_SIZE, LIVE_SIZE, N_SIGNALS, SLOTS, WINDOW
from ml.nets.models import (
    BUMPS,
    CEILING,
    HALF_MAX,
    HALF_MIN,
    STARTUP_CEILING,
    STARTUP_FLOOR,
    VECTOR_SIZE,
    RewardNet,
    StateAutoencoder,
    ZoneNet,
    axis_features,
    draw_requests,
    to_zone,
)
from ml.nets.policy import FixedRule, LearnedPolicy, Oracle
from ml.nets.runtime import DEFAULT_WEIGHTS, Networks
from ml.nets.train import fit
from ml.simulation import generate, save
from ml.simulation.spec import AXES, COMPONENTS, CONTEXT_LENGTH, modality_indices


def test_the_zone_never_leaves_its_guard_rails():
    """Quoi que sorte B, la zone reste dans l'axe, sous les plafonds, et garde une largeur."""
    raw = torch.randn(500, 11) * 25.0  # des sorties extrêmes
    low, high, startup = to_zone(raw)
    ceiling = torch.tensor(CEILING)
    assert (low >= -1e-6).all() and (high <= ceiling + 1e-6).all()
    width = high - low
    assert (width >= 2 * HALF_MIN - 1e-6).all() and (width <= 2 * HALF_MAX + 1e-6).all()
    assert (startup >= STARTUP_FLOOR - 1e-6).all() and (startup <= STARTUP_CEILING + 1e-6).all()

    requests = draw_requests(low, high, startup, samples=4)
    assert requests.shape == (4, 500, len(AXES))
    assert (requests[..., :5] >= low - 1e-6).all() and (requests[..., :5] <= high + 1e-6).all()
    assert (requests[..., 5] <= startup + 1e-6).all()


def test_adding_a_modality_leaves_the_state_unchanged():
    """Une nouvelle source part de zéro : L ne bouge pas tant qu'elle n'est pas entraînée."""
    torch.manual_seed(0)
    model = StateAutoencoder(modality_indices())
    g, p = torch.randn(64, N_SIGNALS), torch.randn(64, N_SIGNALS)
    m = (torch.rand(64, N_SIGNALS) > 0.2).float()
    clock = torch.randn(64, 4)
    before = model.encode(g, p, m, clock)

    new_columns = [N_SIGNALS, N_SIGNALS + 1]  # par exemple deux signaux tirés de la voix
    trainable = model.add_modality("voice", new_columns)
    extra = torch.randn(64, 2)
    wider = [torch.cat([part, extra], dim=1) for part in (g, p)]
    after = model.encode(*wider, torch.cat([m, torch.ones(64, 2)], dim=1), clock)

    assert torch.allclose(before, after, atol=1e-6)
    assert model.decode(after, clock).shape == (64, N_SIGNALS + 2)
    assert sum(parameter.numel() for parameter in trainable) > 0
    with pytest.raises(ValueError):
        model.add_modality("voice", new_columns)


def test_the_zone_network_reads_28_states():
    model = ZoneNet(width=16)
    raw = model(
        torch.randn(5, CONTEXT_LENGTH, len(COMPONENTS) + 4),
        torch.randn(5, LIVE_SIZE),
        torch.zeros(5, VECTOR_SIZE),
    )
    assert raw.shape == (5, 11)


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> tuple[Networks, Path]:
    """Un entraînement minuscule, juste pour faire tourner toute la chaîne."""
    folder = tmp_path_factory.mktemp("nets")
    save(generate(n_people=80, n_days=18, seed=1), folder / "data")
    networks, metrics = fit(
        folder / "data", folder / "weights", epochs=(1, 1, 1), width=16, log=lambda _line: None
    )
    assert set(metrics) == {"autoencoder", "reward", "reward_net", "zone_net"}
    return networks, folder


def _one_week(networks: Networks, n_people: int = 6):
    data = generate(n_people=n_people, n_days=16, seed=5)
    normal = networks.normal(data.theta)
    at = np.full(n_people, 15 * SLOTS + 2)
    index = at[:, None] + WINDOW
    window = data.theta[np.arange(n_people)[:, None], index]
    states, live = networks.states(window, normal, index)
    return states, live[:, -1], index


def _check_answers(networks: Networks) -> None:
    states, live, index = _one_week(networks)
    assert states.shape == (6, CONTEXT_LENGTH, len(COMPONENTS))
    assert ((states > 0) & (states < 1)).all()
    assert live.shape == (6, LIVE_SIZE)

    vectors = np.zeros((6, VECTOR_SIZE), dtype=np.float32)
    low, high, startup = networks.zone(states, index, live, vectors)
    assert low.shape == high.shape == (6, 5) and startup.shape == (6,)
    assert (low < high).all() and (high <= np.array(CEILING) + 1e-6).all()

    value = networks.reward(states[:, 0], states[:, -1])
    assert ((value >= 0) & (value <= 100)).all()
    assert networks.reward(states[:, 0], states[:, 0]) == pytest.approx(50.0)


def test_trained_networks_are_written_reloaded_and_answer(trained):
    networks, folder = trained
    _check_answers(networks)
    again = Networks.load(folder / "weights")
    states, live, index = _one_week(networks)
    same, _, _ = _one_week(again)
    assert np.allclose(states, same, atol=1e-6)
    assert again.meta["parameters"]["total"] > 0


def test_a_patient_vector_starts_at_zero_and_moves_with_reactions(trained):
    networks, _ = trained
    nothing = np.zeros((0, CONTEXT_SIZE), dtype=np.float32)
    nobody = np.zeros(0, dtype=int)
    start = networks.fit_vectors(nobody, nothing, np.zeros((0, 6)), np.zeros(0), np.zeros(0), 3)
    assert start.shape == (3, VECTOR_SIZE) and not start.any()

    rng = np.random.default_rng(0)
    context = rng.normal(size=(40, CONTEXT_SIZE)).astype(np.float32)
    axes = rng.random((40, 6)).astype(np.float32)
    person = np.zeros(40, dtype=int)  # quarante réactions du patient 0, aucune du patient 1
    moved = networks.fit_vectors(person, context, axes, np.full(40, 90.0), np.ones(40), 2)
    assert np.abs(moved[0]).max() > 0 and not moved[1].any()

    chance = networks.reply_chance(context, axes, moved[person])
    assert ((chance > 0) & (chance < 1)).all()


def test_the_reward_network_is_a_committee_that_can_be_cautious():
    """Là où les membres ne sont pas d'accord, l'avis prudent est plus bas que la moyenne."""
    torch.manual_seed(0)
    model = RewardNet(members=4)
    context, vector = torch.randn(9, CONTEXT_SIZE), torch.zeros(9, VECTOR_SIZE)
    axes = torch.rand(9, len(AXES))
    assert model.opinions(context, axes, vector).shape == (4, 9, 2)
    mean = model(context, axes, vector)
    assert (model.cautious(context, axes, vector, caution=1.0) < mean).all()
    assert torch.allclose(model.cautious(context, axes, vector, caution=0.0), mean)
    assert axis_features(axes).shape == (9, len(AXES) * (1 + BUMPS))


def test_every_policy_runs_in_a_closed_loop(trained):
    """B, la règle fixe et l'oracle font vivre des patients sans jamais sortir des garde-fous."""
    networks, _ = trained
    for policy in (LearnedPolicy(networks), FixedRule(networks), Oracle()):
        log = generate(n_people=40, n_days=14, seed=3, policy=policy).episodes
        assert len(log.person) > 0
        assert ((log.axes >= 0) & (log.axes <= 1)).all()
        assert (log.zone_high[:, 2:] <= np.array(CEILING[2:]) + 1e-6).all()
        assert (log.zone_low <= log.zone_high).all()


def test_the_weights_in_the_repository_load_and_answer():
    """Les poids versionnés dans `ml/weights` correspondent aux signaux actuels."""
    networks = Networks.load(DEFAULT_WEIGHTS)
    assert networks.global_mean.shape == (N_SIGNALS,)
    _check_answers(networks)
