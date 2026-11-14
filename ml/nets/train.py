"""Entraîne les trois réseaux sur un jeu simulé (docs/modele.md, section 6).

Usage : uv run python -m ml.nets.train --data ml/data/sim_big --out ml/weights

Les étapes :
1. l'autoencodeur, sur les relevés de tout le monde, puis L_ref sur les personnes saines ;
2. le réseau A et le vecteur de chaque patient, sur le journal d'épisodes ;
3. le réseau B, contre A ;
4. on recommence 2 et 3 après avoir laissé B choisir une partie des zones, pour que A voie
   les régions où B va réellement.

Les personnes sont séparées en trois groupes, par personne et jamais par ligne : 70 % pour
entraîner, 15 % pour régler, 15 % pour le test final (`ml.nets.evaluate`).
"""

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from ml.nets.features import (
    SLOTS,
    WINDOW,
    context_features,
    encoder_inputs,
    global_normal,
    live_features,
    person_normal,
    time_features,
    transform,
)
from ml.nets.models import (
    VECTOR_SIZE,
    RewardNet,
    StateAutoencoder,
    ZoneNet,
    draw_requests,
    to_zone,
)
from ml.nets.runtime import PRIOR, Networks, vector_loss
from ml.simulation import patient, population, subset
from ml.simulation.episodes import Moment, Zones, _random_zones, simulate_policy
from ml.simulation.people import HEALTHY, PATIENT
from ml.simulation.reward import distance, reference, reward
from ml.simulation.spec import COMPONENTS, REWARD_DELAY_DAYS, modality_indices

SUPERVISED_WEIGHT = 30.0  # poids de la tête supervisée face à la reconstruction
MASK_RATE = 0.2  # part des signaux cachés à l'autoencodeur pendant l'entraînement
MODALITY_DROP = 0.15  # probabilité de cacher une modalité entière
VECTOR_DROP = 0.3  # part des exemples où B est entraîné sans vecteur : le cas d'un nouveau patient
WIDTH_BONUS = 0.03  # ce que B gagne à garder une zone large, en récompense divisée par 100
CAUTION = 1.0  # B suit la moyenne du comité A, moins ce nombre de fois son désaccord
SAMPLES = 8  # demandes tirées dans chaque zone pour noter B
EXPLORE_SHARE = 0.7  # part des zones choisies par B quand on refait un journal
REWARD_STEP = SLOTS * REWARD_DELAY_DAYS


@dataclass
class Prepared:
    """Un jeu simulé, prêt pour les réseaux."""

    g: np.ndarray  # [n, t, s] signaux par rapport à tout le monde
    p: np.ndarray  # [n, t, s] signaux par rapport à la normale de la personne
    m: np.ndarray  # [n, t, s] 1 = présent
    time: np.ndarray  # [t, 4]
    hidden: np.ndarray  # [n, t, 6] état caché, cible de la tête supervisée
    group: np.ndarray  # [n]
    split: dict[str, np.ndarray]  # indices des personnes : train, val, test
    global_mean: np.ndarray
    global_spread: np.ndarray
    episodes: dict[str, np.ndarray]


def split_people(n_people: int, seed: int) -> dict[str, np.ndarray]:
    order = np.random.default_rng(seed).permutation(n_people)
    first, second = int(0.70 * n_people), int(0.85 * n_people)
    parts = {"train": order[:first], "val": order[first:second], "test": order[second:]}
    return {name: np.sort(index) for name, index in parts.items()}


def prepare(data_dir: Path, seed: int = 0) -> Prepared:
    people = np.load(data_dir / "people.npz")
    values = transform(people["theta"])
    split = split_people(len(values), seed)
    global_mean, global_spread = global_normal(values[split["train"]])
    normal = person_normal(values, global_mean, global_spread)
    g, p, m = encoder_inputs(values, global_mean, global_spread, *normal)
    with np.load(data_dir / "episodes.npz") as log:
        episodes = {name: log[name] for name in log.files}
    return Prepared(
        g=g,
        p=p,
        m=m,
        time=time_features(np.arange(values.shape[1])),
        hidden=people["state"].astype(np.float32),
        group=people["group"],
        split=split,
        global_mean=global_mean,
        global_spread=global_spread,
        episodes=episodes,
    )


def _rows(prepared: Prepared, people: np.ndarray) -> list[torch.Tensor]:
    """Toutes les lignes (une par relevé) des personnes données : g, p, m, heure, état caché."""
    n_signals = prepared.g.shape[-1]
    arrays = [
        prepared.g[people].reshape(-1, n_signals),
        prepared.p[people].reshape(-1, n_signals),
        prepared.m[people].reshape(-1, n_signals),
        np.tile(prepared.time, (len(people), 1)),
        prepared.hidden[people].reshape(-1, len(COMPONENTS)),
    ]
    return [torch.from_numpy(np.ascontiguousarray(array)) for array in arrays]


def _hide(
    m: torch.Tensor, columns: dict[str, list[int]], generator: torch.Generator
) -> torch.Tensor:
    """Ce que l'autoencodeur voit : on cache des signaux isolés et des modalités entières."""
    keep = (torch.rand(m.shape, generator=generator) > MASK_RATE).float()
    for signal_columns in columns.values():
        whole = (torch.rand(len(m), 1, generator=generator) > MODALITY_DROP).float()
        keep[:, signal_columns] *= whole
    return keep


# --- 1. L'autoencodeur -----------------------------------------------------------------------


def train_autoencoder(
    prepared: Prepared, epochs: int, seed: int = 0, batch: int = 2048, log=print
) -> StateAutoencoder:
    generator = torch.Generator().manual_seed(seed)
    torch.manual_seed(seed)
    g, p, m, clock, hidden = _rows(prepared, prepared.split["train"])
    model = StateAutoencoder(modality_indices())
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-5)
    steps = epochs * math.ceil(len(g) / batch)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=2e-3, total_steps=steps)
    for epoch in range(epochs):
        order = torch.randperm(len(g), generator=generator)
        totals = np.zeros(2)
        for start in range(0, len(g), batch):
            rows = order[start : start + batch]
            seen = m[rows]
            keep = _hide(seen, model.columns, generator)
            state = model.encode(g[rows] * keep, p[rows] * keep, seen * keep, clock[rows])
            rebuilt = model.decode(state, clock[rows])
            gap = F.smooth_l1_loss(rebuilt, p[rows], reduction="none")
            rebuild_loss = (gap * seen).sum() / seen.sum().clamp(min=1.0)
            state_loss = F.mse_loss(state, hidden[rows])
            loss = rebuild_loss + SUPERVISED_WEIGHT * state_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            schedule.step()
            totals += [rebuild_loss.item(), state_loss.item()]
        count = math.ceil(len(g) / batch)
        rebuild, state_rmse = totals[0] / count, math.sqrt(totals[1] / count)
        log(
            f"  autoencodeur {epoch + 1}/{epochs} :"
            f" reconstruction {rebuild:.3f}, état {state_rmse:.3f}"
        )
    return model.eval()


def autoencoder_metrics(model: StateAutoencoder, prepared: Prepared, people: np.ndarray) -> dict:
    """Sur des personnes jamais vues : l'écart entre L et l'état caché, et la reconstruction."""
    g, p, m, clock, hidden = _rows(prepared, people)
    generator = torch.Generator().manual_seed(1)

    def state_error(keep: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            state = model.encode(g * keep, p * keep, m * keep, clock)
        return ((state - hidden) ** 2).mean(dim=0).sqrt()

    everything = torch.ones_like(m)
    full = state_error(everything)
    views = {"all": full}
    for name, signal_columns in model.columns.items():
        without = everything.clone()
        without[:, signal_columns] = 0.0
        views[f"without_{name}"] = state_error(without)
        only = torch.zeros_like(m)
        only[:, signal_columns] = 1.0
        views[f"only_{name}"] = state_error(only)

    keep = (torch.rand(m.shape, generator=generator) > MASK_RATE).float()
    hidden_cells = m * (1.0 - keep)
    with torch.no_grad():
        rebuilt = model.decode(model.encode(g * keep, p * keep, m * keep, clock), clock)
    rebuilt_error = (((rebuilt - p) ** 2) * hidden_cells).sum() / hidden_cells.sum()
    baseline = ((p**2) * hidden_cells).sum() / hidden_cells.sum()
    return {
        "state_rmse": {name: round(float(v), 4) for name, v in zip(COMPONENTS, full, strict=True)},
        "state_rmse_mean": round(float(full.mean()), 4),
        # Ce que vaudrait une réponse « au hasard » : la dispersion de l'état caché.
        "state_spread_mean": round(float(hidden.std(dim=0).mean()), 4),
        "state_rmse_by_view": {name: round(float(v.mean()), 4) for name, v in views.items()},
        "masked_reconstruction_mse": round(float(rebuilt_error), 4),
        "masked_reconstruction_baseline": round(float(baseline), 4),
    }


def encode_everyone(model: StateAutoencoder, prepared: Prepared) -> np.ndarray:
    """L de chaque relevé de chaque personne : [n, t, 6]."""
    n_people, n_snapshots, n_signals = prepared.g.shape
    clock = torch.from_numpy(np.tile(prepared.time, (n_people, 1)))
    arrays = [
        torch.from_numpy(a.reshape(-1, n_signals)) for a in (prepared.g, prepared.p, prepared.m)
    ]
    parts = []
    with torch.no_grad():
        for start in range(0, len(clock), 65536):
            piece = [array[start : start + 65536] for array in arrays]
            parts.append(model.encode(*piece, clock[start : start + 65536]))
    return torch.cat(parts).numpy().reshape(n_people, n_snapshots, -1)


# --- 2. Le journal vu par les réseaux --------------------------------------------------------


@dataclass
class Journal:
    """Une ligne par demande du journal, sous la forme que lisent A et B."""

    person: np.ndarray  # [m]
    day: np.ndarray  # [m]
    context: np.ndarray  # [m, 32] entrée de A
    sequence: np.ndarray  # [m, 28, 10] entrée de B : 28 états et leur heure
    live: np.ndarray  # [m, 12] comportement en direct
    axes: np.ndarray  # [m, 6] la demande envoyée
    target: np.ndarray  # [m] récompense que A apprend, divisée par 100
    replied: np.ndarray  # [m] 1 si le patient a répondu
    hidden_reward: np.ndarray  # [m] récompense calculée sur l'état caché (0 à 100)
    counterfactual: np.ndarray  # [m] récompense contre l'état attendu sans la demande

    def take(self, rows: np.ndarray) -> "Journal":
        return Journal(**{f.name: getattr(self, f.name)[rows] for f in fields(self)})

    def of(self, people: np.ndarray) -> "Journal":
        """Les lignes qui concernent ces personnes."""
        return self.take(np.flatnonzero(np.isin(self.person, people)))

    @staticmethod
    def join(parts: list["Journal"]) -> "Journal":
        names = [f.name for f in fields(Journal)]
        return Journal(**{n: np.concatenate([getattr(part, n) for part in parts]) for n in names})

    def __len__(self) -> int:
        return len(self.person)


def latent_reward(
    states: np.ndarray,
    l_ref: tuple[np.ndarray, np.ndarray],
    log: dict[str, np.ndarray],
    measure: str,
) -> np.ndarray:
    """Récompense (0 à 100) calculée sur L, comme dans la vraie vie.

    `slot` : L au moment de la demande contre L vingt-quatre heures plus tard.
    `day` : la moyenne de L sur la journée de la demande contre celle du lendemain. Quatre
    relevés au lieu d'un : la mesure est moins bruitée.
    """
    person, day = log["person"], log["day"]
    if measure == "day":
        daily = states.reshape(len(states), -1, SLOTS, states.shape[-1]).mean(axis=2)
        before, after = daily[person, day], daily[person, day + REWARD_DELAY_DAYS]
    else:
        at = day * SLOTS + log["slot"]
        before, after = states[person, at], states[person, at + REWARD_STEP]
    return reward(distance(before, *l_ref), distance(after, *l_ref))


def build_journal(
    prepared: Prepared,
    states: np.ndarray,
    l_ref: tuple[np.ndarray, np.ndarray],
    measure: str = "slot",
) -> Journal:
    """`measure` : `slot` ou `day` (voir `latent_reward`), ou `hidden` pour la récompense
    calculée sur l'état caché, qui n'existe qu'en simulation."""
    log = prepared.episodes
    person, slot = log["person"], log["slot"]
    at = log["day"] * SLOTS + slot
    window = at[:, None] + WINDOW
    recent = states[person[:, None], window]
    live = live_features(prepared.p[person, at], prepared.m[person, at])
    if measure == "hidden":
        target = log["reward"] / 100.0
    else:
        target = latent_reward(states, l_ref, log, measure) / 100.0
    return Journal(
        person=person,
        day=log["day"],
        context=context_features(recent, live, slot),
        sequence=np.concatenate([recent, time_features(window)], axis=-1).astype(np.float32),
        live=live.astype(np.float32),
        axes=log["axes"].astype(np.float32),
        target=target.astype(np.float32),
        replied=log["replied"].astype(np.float32),
        hidden_reward=log["reward"],
        counterfactual=log["reward_counterfactual"],
    )


# --- 3. Le réseau A et les vecteurs des patients ---------------------------------------------


def train_reward_net(
    journal: Journal, n_people: int, epochs: int, seed: int = 0, prior: float = PRIOR, log=print
) -> tuple[RewardNet, np.ndarray]:
    """Régression sur le journal. Les poids de A et les vecteurs s'apprennent ensemble.

    Chaque membre du comité voit le journal avec ses propres poids d'échantillonnage : ils ne
    font pas les mêmes erreurs, et leur désaccord dit où A ne sait pas.
    """
    generator = torch.Generator().manual_seed(seed)
    torch.manual_seed(seed)
    batch = 1024
    person = torch.from_numpy(journal.person.astype(np.int64))
    context, axes = torch.from_numpy(journal.context), torch.from_numpy(journal.axes)
    target, answered = torch.from_numpy(journal.target), torch.from_numpy(journal.replied)
    count = torch.from_numpy(np.bincount(journal.person, minlength=n_people).clip(1)).float()
    model = RewardNet()
    weight = torch.poisson(torch.ones(len(model.members), len(journal)), generator=generator)
    vectors = nn.Embedding(n_people, VECTOR_SIZE)
    nn.init.zeros_(vectors.weight)
    optimizer = torch.optim.AdamW(
        [
            {"params": model.parameters(), "weight_decay": 1e-4},
            {"params": vectors.parameters(), "weight_decay": 0.0},
        ],
        lr=2e-3,
    )
    steps = epochs * math.ceil(len(journal) / batch)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=2e-3, total_steps=steps)
    for epoch in range(epochs):
        order = torch.randperm(len(journal), generator=generator)
        total = 0.0
        for start in range(0, len(journal), batch):
            pick = order[start : start + batch]
            own = vectors(person[pick])
            opinions = model.opinions(context[pick], axes[pick], own)
            error = vector_loss(opinions, target[pick], answered[pick])
            # Le vecteur est retenu près de zéro, d'autant plus que le patient a peu de lignes.
            held = prior * (own**2).sum(dim=-1) / count[person[pick]]
            loss = (weight[:, pick] * error).mean() + held.mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            schedule.step()
            total += ((opinions[..., 0].mean(dim=0) - target[pick]) ** 2).mean().item()
        if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
            rmse = 100.0 * math.sqrt(total / math.ceil(len(journal) / batch))
            log(f"  réseau A {epoch + 1}/{epochs} : erreur {rmse:.2f} points")
    return model.eval(), vectors.weight.detach().numpy().copy()


def reward_net_metrics(networks: Networks, journal: Journal, seed: int = 0) -> dict:
    """Sur des patients jamais vus. Leur vecteur est appris sur leurs premières semaines.

    L'« avantage » d'une demande est ce que A en attend de plus que d'une demande au hasard dans
    le même contexte. C'est ce qui guide B, et c'est donc lui qu'on compare à la vérité.
    """
    rng = np.random.default_rng(seed)
    early = journal.day < np.quantile(journal.day, 0.6)
    late = ~early
    person, context, axes = journal.person, journal.context, journal.axes
    target = 100.0 * journal.target
    n_people = int(person.max()) + 1
    nobody = np.zeros((len(journal), VECTOR_SIZE), dtype=np.float32)
    vectors = networks.fit_vectors(
        person[early], context[early], axes[early], target[early], journal.replied[early], n_people
    )
    general = networks.predict(context, axes, nobody)
    personal = networks.predict(context, axes, vectors[person])

    def rmse(prediction: np.ndarray) -> float:
        return round(float(np.sqrt(((prediction - target)[late] ** 2).mean())), 2)

    def reply_error(own: np.ndarray) -> float:
        chance = np.clip(networks.reply_chance(context[late], axes[late], own[late]), 1e-4, 0.9999)
        answered = journal.replied[late]
        return round(
            float(-(answered * np.log(chance) + (1 - answered) * np.log(1 - chance)).mean()), 4
        )

    def advantage(own: np.ndarray) -> np.ndarray:
        elsewhere = []
        for _ in range(8):
            low, high, cap = _random_zones(rng, len(journal))
            inside = low + rng.random(low.shape) * (high - low)
            other = np.concatenate([inside, (rng.random(len(cap)) * cap)[:, None]], axis=1)
            elsewhere.append(networks.predict(context, other.astype(np.float32), own))
        return networks.predict(context, axes, own) - np.mean(elsewhere, axis=0)

    truth = journal.counterfactual
    report = {
        "rmse_constant": rmse(np.full(len(journal), target[early].mean())),
        "rmse_general": rmse(general),
        "rmse_personal": rmse(personal),
        "reply_error_general": reply_error(nobody),
        "reply_error_personal": reply_error(vectors[person]),
    }
    for name, own in (("general", nobody), ("personal", vectors[person])):
        gain = advantage(own)[late]
        order = np.argsort(gain)
        fifth = len(order) // 5
        report |= {
            f"advantage_correlation_{name}": round(float(np.corrcoef(gain, truth[late])[0, 1]), 3),
            # Ce que valent vraiment les demandes que A préfère, et celles qu'il déconseille.
            f"true_reward_top_fifth_{name}": round(float(truth[late][order[-fifth:]].mean()), 2),
            f"true_reward_bottom_fifth_{name}": round(float(truth[late][order[:fifth]].mean()), 2),
        }
    return report


# --- 4. Le réseau B --------------------------------------------------------------------------


def train_zone_net(
    journal: Journal,
    reward_net: RewardNet,
    vectors: np.ndarray,
    width: int,
    epochs: int,
    seed: int = 0,
    log=print,
) -> ZoneNet:
    """B propose une zone, on tire des demandes dedans, A les note, et B suit la note prudente."""
    generator = torch.Generator().manual_seed(seed)
    torch.manual_seed(seed)
    batch = 512
    for parameter in reward_net.parameters():
        parameter.requires_grad_(False)
    sequence, live = torch.from_numpy(journal.sequence), torch.from_numpy(journal.live)
    context = torch.from_numpy(journal.context)
    own = torch.from_numpy(vectors[journal.person].astype(np.float32))
    model = ZoneNet(width)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    steps = epochs * math.ceil(len(journal) / batch)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=1e-3, total_steps=steps)
    for epoch in range(epochs):
        order = torch.randperm(len(journal), generator=generator)
        total, widths = 0.0, 0.0
        for start in range(0, len(journal), batch):
            pick = order[start : start + batch]
            known = (torch.rand(len(pick), 1, generator=generator) > VECTOR_DROP).float()
            vector = own[pick] * known
            low, high, startup = to_zone(model(sequence[pick], live[pick], vector))
            requests = draw_requests(low, high, startup, SAMPLES)
            score = reward_net.cautious(
                context[pick].expand(SAMPLES, -1, -1),
                requests,
                vector.expand(SAMPLES, -1, -1),
                CAUTION,
            )
            half = (high - low).mean() / 2.0
            loss = -score.mean() - WIDTH_BONUS * half
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            schedule.step()
            total += score.mean().item()
            widths += half.item()
        count = math.ceil(len(journal) / batch)
        log(
            f"  réseau B {epoch + 1}/{epochs} : note prudente de A {100 * total / count:.2f},"
            f" demi-largeur {widths / count:.3f}"
        )
    return model.eval()


def zone_net_metrics(networks: Networks, journal: Journal, seed: int = 0) -> dict:
    """Ce que A pense des zones de B, contre des zones au hasard. Ce n'est pas encore la vérité :
    la vraie mesure est la boucle fermée de `ml.nets.evaluate`."""
    rng = np.random.default_rng(seed)
    nobody = np.zeros((len(journal), VECTOR_SIZE), dtype=np.float32)
    sequence, live = torch.from_numpy(journal.sequence), torch.from_numpy(journal.live)
    with torch.no_grad():
        raw = networks.zone_net(sequence, live, torch.from_numpy(nobody))
        low, high, startup = (part.numpy() for part in to_zone(raw))

    def note(zone_low: np.ndarray, zone_high: np.ndarray, cap: np.ndarray) -> float:
        inside = zone_low + rng.random(zone_low.shape) * (zone_high - zone_low)
        axes = np.concatenate([inside, (rng.random(len(cap)) * cap)[:, None]], axis=1)
        return float(networks.predict(journal.context, axes.astype(np.float32), nobody).mean())

    return {
        "predicted_reward_learned": round(note(low, high, startup), 2),
        "predicted_reward_random": round(note(*_random_zones(rng, len(journal))), 2),
        "half_width_by_axis": [round(float(v), 3) for v in ((high - low) / 2.0).mean(axis=0)],
        "center_by_axis": [round(float(v), 3) for v in ((high + low) / 2.0).mean(axis=0)],
        "center_spread_by_axis": [round(float(v), 3) for v in ((high + low) / 2.0).std(axis=0)],
        "startup_cap": round(float(startup.mean()), 3),
    }


# --- 5. Refaire un journal là où B va --------------------------------------------------------


class _Mixed:
    """Pour refaire un journal : B choisit la plupart des zones, le hasard choisit les autres."""

    def __init__(self, learned, rng: np.random.Generator, share: float) -> None:
        self.learned, self.rng, self.share = learned, rng, share

    def zones(self, moment: Moment) -> Zones:
        chosen = self.learned.zones(moment)
        random = _random_zones(self.rng, len(moment.slot))
        by_b = self.rng.random(len(moment.slot)) < self.share
        low = np.where(by_b[:, None], chosen[0], random[0])
        high = np.where(by_b[:, None], chosen[1], random[1])
        return low, high, np.where(by_b, chosen[2], random[2])

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None:
        return None


def explore(
    networks: Networks,
    data_dir: Path,
    people_index: np.ndarray,
    measure: str,
    seed: int,
    policy=None,
) -> Journal:
    """Fait vivre ces personnes avec B aux commandes d'une partie des zones, et rend le journal.

    Les numéros de personne du journal sont ceux du jeu d'origine : les vecteurs restent alignés.
    """
    from ml.nets.policy import LearnedPolicy  # évite un import circulaire

    setup = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    _, people, rules, hidden_ref = population(
        setup["n_people"], setup["n_days"], setup["healthy_share"], setup["seed"]
    )
    people, rules = subset(people, rules, people_index)
    rng = np.random.default_rng([setup["seed"], seed, 7])
    if policy is None:
        policy = _Mixed(LearnedPolicy(networks, personal=False), rng, EXPLORE_SHARE)
    state, theta, log = simulate_policy(rng, people, rules, hidden_ref, policy)

    values = transform(theta)
    normal = person_normal(values, networks.global_mean, networks.global_spread)
    g, p, m = encoder_inputs(values, networks.global_mean, networks.global_spread, *normal)
    clock = time_features(np.arange(values.shape[1]))
    states = networks.encode(g, p, m, np.broadcast_to(clock, (*g.shape[:-1], 4)))
    lived = Prepared(
        g=g,
        p=p,
        m=m,
        time=clock,
        hidden=np.repeat(state, SLOTS, axis=1).astype(np.float32),
        group=people.group,
        split={},
        global_mean=networks.global_mean,
        global_spread=networks.global_spread,
        episodes=asdict(log),
    )
    l_ref = (networks.reference_mean, networks.reference_spread)
    journal = build_journal(lived, states, l_ref, measure)
    journal.person = people_index[journal.person]
    return journal


# --- Tout enchaîner ---------------------------------------------------------------------------


def fit(
    data_dir: Path,
    out_dir: Path | None,
    seed: int = 0,
    epochs: tuple[int, int, int] = (12, 30, 3),
    width: int = 32,
    measure: str = "slot",
    rounds: int = 2,
    autoencoder_from: Path | None = None,
    prior: float = PRIOR,
    log=print,
) -> tuple[Networks, dict]:
    """Entraîne les trois réseaux, les écrit dans `out_dir` et renvoie les mesures.

    `measure` choisit la récompense que A apprend : `slot`, `day` ou `hidden` (`build_journal`).
    `rounds` : nombre de passages A puis B. Entre deux passages, on refait un journal où B
    choisit une partie des zones. `autoencoder_from` reprend un autoencodeur déjà entraîné.
    """
    started = time.perf_counter()
    prepared = prepare(data_dir, seed)
    train, val = prepared.split["train"], prepared.split["val"]
    n_people = len(prepared.group)
    log(
        f"Données : {n_people} personnes, {prepared.g.shape[1]} relevés,"
        f" {prepared.g.shape[2]} signaux"
    )

    if autoencoder_from is None:
        autoencoder = train_autoencoder(prepared, epochs[0], seed, log=log)
    else:
        autoencoder = StateAutoencoder(modality_indices())
        saved = torch.load(autoencoder_from / "autoencoder.pt", weights_only=True)
        autoencoder.load_state_dict(saved)
        autoencoder.eval()
    metrics = {"autoencoder": autoencoder_metrics(autoencoder, prepared, val)}
    states = encode_everyone(autoencoder, prepared)
    l_ref = reference(states[train[prepared.group[train] == HEALTHY]])
    l_ref = (l_ref[0].astype(np.float32), l_ref[1].astype(np.float32))

    everything = build_journal(prepared, states, l_ref, measure)
    journal, journal_val = everything.of(train), everything.of(val)
    truth = journal_val.hidden_reward
    metrics["reward"] = {
        "measure": measure,
        "episodes_train": len(journal),
        "episodes_val": len(journal_val),
        "std_on_hidden_state": round(float(truth.std()), 2),
    }
    for name in ("slot", "day"):
        measured = latent_reward(states, l_ref, prepared.episodes, name)
        measured = measured[np.isin(prepared.episodes["person"], val)]
        metrics["reward"][f"std_on_L_{name}"] = round(float(measured.std()), 2)
        link = round(float(np.corrcoef(measured, truth)[0, 1]), 3)
        metrics["reward"][f"correlation_with_hidden_{name}"] = link
        log(f"Récompense sur L ({name}) contre l'état caché : corrélation {link:.2f}")

    patients = train[prepared.group[train] == PATIENT]
    networks = None
    for turn in range(rounds):
        log(f"Passage {turn + 1}/{rounds} : {len(journal)} lignes de journal")
        reward_net, vectors = train_reward_net(
            journal, n_people, epochs[1], seed + turn, prior, log=log
        )
        zone_net = train_zone_net(
            journal, reward_net, vectors, width, epochs[2], seed + turn, log=log
        )
        networks = Networks(
            autoencoder,
            reward_net,
            zone_net,
            prepared.global_mean,
            prepared.global_spread,
            *l_ref,
            {"trained_on": {"reward_measure": measure, "prior": prior}},
        )
        if turn < rounds - 1:
            journal = Journal.join([journal, explore(networks, data_dir, patients, measure, turn)])
    assert networks is not None

    metrics["reward"]["episodes_train_final"] = len(journal)
    metrics["reward_net"] = reward_net_metrics(networks, journal_val, seed)
    metrics["zone_net"] = zone_net_metrics(networks, journal_val, seed)
    sizes = {
        "autoencoder": sum(p.numel() for p in networks.autoencoder.parameters()),
        "reward_net": sum(p.numel() for p in networks.reward_net.parameters()),
        "zone_net": sum(p.numel() for p in networks.zone_net.parameters()),
    }
    networks.meta = {
        "trained_on": {
            "data": str(data_dir).replace("\\", "/"),
            "seed": seed,
            "people": n_people,
            "epochs": list(epochs),
            "rounds": rounds,
            "reward_measure": measure,
            "prior": prior,
            "minutes": round((time.perf_counter() - started) / 60.0, 1),
        },
        "parameters": sizes | {"total": sum(sizes.values())},
        "metrics": metrics,
        "warning": "Entraîné sur des données simulées : ces réseaux ne savent que ce que"
        " ml/simulation contient.",
    }
    if out_dir is not None:
        networks.save(out_dir)
    return networks, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraîne l'autoencodeur, A et B.")
    parser.add_argument("--data", type=Path, default=Path("ml/data/sim_big"))
    parser.add_argument("--out", type=Path, default=Path("ml/weights"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--epochs", type=int, nargs=3, default=(12, 30, 3), metavar=("AE", "A", "B")
    )
    parser.add_argument("--width", type=int, default=32, help="largeur du Transformer B")
    parser.add_argument("--rounds", type=int, default=2, help="passages A puis B")
    parser.add_argument(
        "--measure",
        choices=("slot", "day", "hidden"),
        default="slot",
        help="récompense apprise par A : sur L au même relevé, sur L en moyenne sur la journée,"
        " ou sur l'état caché (simulation seulement)",
    )
    parser.add_argument(
        "--autoencoder-from", type=Path, default=None, help="reprendre un autoencodeur entraîné"
    )
    parser.add_argument(
        "--prior", type=float, default=PRIOR, help="force qui retient les vecteurs près de zéro"
    )
    args = parser.parse_args()
    networks, metrics = fit(
        args.data,
        args.out,
        args.seed,
        tuple(args.epochs),
        args.width,
        args.measure,
        args.rounds,
        args.autoencoder_from,
        args.prior,
    )
    print(json.dumps(networks.meta["parameters"], indent=2))
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"Poids écrits dans {args.out}")


if __name__ == "__main__":
    main()
