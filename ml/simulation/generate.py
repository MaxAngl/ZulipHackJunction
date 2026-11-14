"""Assemble le jeu de données simulé et l'écrit sur disque.

Trois fichiers :
- people.npz : θ, son masque, l'état caché, le groupe et le parcours de chaque personne, L_ref ;
- episodes.npz : le journal des demandes ;
- meta.json : le nom, l'unité et le sens de chaque colonne, et les réglages utilisés.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from ml.simulation import episodes as episode_log
from ml.simulation import patient
from ml.simulation.people import COURSES, HEALTHY, PATIENT, People, draw_people, observe
from ml.simulation.reward import distance, reference
from ml.simulation.spec import (
    AXES,
    COMPONENTS,
    CONTEXT_DAYS,
    CONTEXT_LENGTH,
    REWARD_DELAY_DAYS,
    SIGNALS,
    SNAPSHOT_HOURS,
    modality_indices,
)


@dataclass(frozen=True)
class Dataset:
    theta: np.ndarray  # [n, jours x 4, signaux] données brutes, NaN = absente
    mask: np.ndarray  # [n, jours x 4, signaux] True = donnée présente
    state: np.ndarray  # [n, jours x 4, 6] état caché au moment de chaque relevé
    group: np.ndarray  # [n] 0 = sain, 1 = patient
    course: np.ndarray  # [n] indice dans COURSES
    reference_mean: np.ndarray  # [6] L_ref : moyenne des personnes saines
    reference_spread: np.ndarray  # [6] L_ref : leur dispersion
    episodes: episode_log.Episodes
    meta: dict


def population(
    n_people: int, n_days: int, healthy_share: float, seed: int
) -> tuple[np.random.Generator, People, patient.Rules, tuple[np.ndarray, np.ndarray]]:
    """Les personnes, leurs règles cachées et L_ref. La même graine redonne les mêmes."""
    shortest = CONTEXT_DAYS + REWARD_DELAY_DAYS + 1
    if n_days < shortest:
        raise ValueError(f"Il faut au moins {shortest} jours : une semaine de contexte d'abord.")
    rng = np.random.default_rng(seed)
    people = draw_people(rng, n_people, n_days, healthy_share)
    rules = patient.draw_rules(rng, n_people)
    # Les personnes saines ne reçoivent pas de demandes : leur état naturel suffit pour L_ref.
    l_ref = reference(people.natural[people.group == HEALTHY])
    return rng, people, rules, l_ref


def subset(people: People, rules: patient.Rules, index: np.ndarray) -> tuple[People, patient.Rules]:
    """Les mêmes personnes, réduites à `index` : pour évaluer sur un groupe mis de côté."""
    traits = {name: values[index] for name, values in people.traits.items()}
    kept = People(people.group[index], people.course[index], people.natural[index], traits)
    return kept, patient.Rules(**{name: values[index] for name, values in asdict(rules).items()})


def generate(
    n_people: int = 600,
    n_days: int = 56,
    healthy_share: float = 0.4,
    seed: int = 0,
    policy: episode_log.Policy | None = None,
) -> Dataset:
    """Génère un jeu complet. La même graine donne exactement les mêmes données.

    Sans politique, les zones sont tirées au hasard. Avec une politique, elle choisit les zones
    jour après jour en ne voyant que les relevés déjà faits.
    """
    rng, people, rules, l_ref = population(n_people, n_days, healthy_share, seed)
    if policy is None:
        daily_state, log = episode_log.simulate(rng, people, rules, l_ref)
        theta = observe(rng, people, daily_state)
    else:
        daily_state, theta, log = episode_log.simulate_policy(rng, people, rules, l_ref, policy)
    state = np.repeat(daily_state, len(SNAPSHOT_HOURS), axis=1).astype(np.float32)
    meta = {
        "seed": seed,
        "n_people": n_people,
        "n_days": n_days,
        "healthy_share": healthy_share,
        "snapshot_hours": list(SNAPSHOT_HOURS),
        "context_length": CONTEXT_LENGTH,
        "reward_delay_days": REWARD_DELAY_DAYS,
        "signals": [asdict(signal) | {"modality": signal.modality} for signal in SIGNALS],
        "modalities": {
            name: [SIGNALS[index].name for index in columns]
            for name, columns in modality_indices().items()
        },
        "components": list(COMPONENTS),
        "axes": list(AXES),
        "groups": {"healthy": HEALTHY, "patient": PATIENT},
        "courses": list(COURSES),
        "reward": "50 + 150 * (d_before - d_after) / (d_before + 1), ramenée entre 0 et 100",
        "warning": "Données simulées : elles ne contiennent que les règles de ml/simulation.",
    }
    return Dataset(
        theta=theta,
        mask=~np.isnan(theta),
        state=state,
        group=people.group,
        course=people.course,
        reference_mean=l_ref[0].astype(np.float32),
        reference_spread=l_ref[1].astype(np.float32),
        episodes=log,
        meta=meta,
    )


def save(dataset: Dataset, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "people.npz",
        theta=dataset.theta,
        mask=dataset.mask,
        state=dataset.state,
        group=dataset.group,
        course=dataset.course,
        reference_mean=dataset.reference_mean,
        reference_spread=dataset.reference_spread,
    )
    np.savez_compressed(out_dir / "episodes.npz", **asdict(dataset.episodes))
    text = json.dumps(dataset.meta, indent=2, ensure_ascii=False) + "\n"
    (out_dir / "meta.json").write_text(text, encoding="utf-8", newline="\n")


def summary(dataset: Dataset) -> str:
    """Quelques chiffres pour vérifier d'un coup d'œil que le jeu a du sens."""
    log, healthy = dataset.episodes, dataset.group == HEALTHY
    l_ref = (dataset.reference_mean, dataset.reference_spread)
    gap = distance(dataset.state, *l_ref).mean(axis=1)
    heavy, light = log.overload > 0.2, log.overload == 0
    lines = [
        f"Personnes : {len(dataset.group)} ({healthy.sum()} saines, {(~healthy).sum()} patients)",
        f"Relevés par personne : {dataset.theta.shape[1]}, signaux : {dataset.theta.shape[2]}",
        f"Données absentes : {100 * (1 - dataset.mask.mean()):.1f} %",
        f"Distance à L_ref : saines {gap[healthy].mean():.2f}, patients {gap[~healthy].mean():.2f}",
        f"Demandes : {len(log.person)}, taux de réponse {100 * log.replied.mean():.0f} %",
        f"Récompense moyenne : {log.reward.mean():.1f} (écart-type {log.reward.std():.1f})",
        f"  demandes supportables : {log.reward_counterfactual[light].mean():.1f}"
        f" ({100 * log.replied[light].mean():.0f} % de réponses)",
        f"  demandes trop lourdes : {log.reward_counterfactual[heavy].mean():.1f}"
        f" ({100 * log.replied[heavy].mean():.0f} % de réponses)",
    ]
    return "\n".join(lines)
