"""Compare le réseau B à ses références, en boucle fermée, sur des patients jamais vus.

Usage : uv run python -m ml.nets.evaluate --data ml/data/sim_big --weights ml/weights

Les patients de test sont ceux que l'entraînement n'a pas utilisés. Chaque politique fait vivre
les mêmes patients, avec les mêmes tirages : seules les zones changent. La récompense affichée
est la vraie, calculée sur l'état caché du simulateur, que les réseaux ne voient jamais.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from ml.nets.policy import FixedRule, LearnedPolicy, Oracle
from ml.nets.runtime import Networks
from ml.nets.train import split_people
from ml.simulation import population, subset
from ml.simulation.episodes import Episodes, Policy, RandomZones, simulate_policy
from ml.simulation.people import PATIENT

LABELS = {
    "random": "Zone au hasard",
    "fixed_rule": "Règle fixe actuelle",
    "learned_general": "Réseau B, sans vecteur personnel",
    "learned": "Réseau B, avec vecteur personnel",
    "oracle": "Oracle (lit la vérité cachée)",
}


def _summary(log: Episodes, state: np.ndarray, natural: np.ndarray) -> dict:
    weeks = log.day // 7
    by_week = [
        round(float(log.reward_counterfactual[weeks == week].mean()), 2)
        for week in range(int(weeks.min()), int(weeks.max()) + 1)
    ]
    last = slice(-28, None)
    return {
        "requests": int(len(log.person)),
        "reward": round(float(log.reward.mean()), 2),
        "reward_counterfactual": round(float(log.reward_counterfactual.mean()), 2),
        "reply_rate": round(float(log.replied.mean()), 3),
        "overload_rate": round(float((log.overload > 0).mean()), 3),
        "fit": round(float(log.fit.mean()), 3),
        # Ce que les demandes ont ajouté à l'état des patients, sur les quatre dernières semaines.
        "state_lift": round(float(100.0 * (state[:, last] - natural[:, last]).mean()), 2),
        "reward_counterfactual_by_week": by_week,
    }


def evaluate(
    data_dir: Path,
    weights_dir: Path,
    limit: int | None = None,
    split_seed: int = 0,
    fresh_seed: int | None = None,
) -> dict:
    """Fait tourner chaque politique sur des patients que l'entraînement n'a pas vus.

    Par défaut, ce sont les patients de test du jeu `data_dir`. Avec `fresh_seed`, ce sont des
    personnes entièrement nouvelles, tirées avec une autre graine : c'est le test à ne regarder
    qu'une fois, quand tous les réglages sont arrêtés.
    """
    networks = Networks.load(weights_dir)
    setup = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    seed = setup["seed"] if fresh_seed is None else fresh_seed
    n_people = setup["n_people"] if fresh_seed is None else 1500
    _, people, rules, l_ref = population(n_people, setup["n_days"], setup["healthy_share"], seed)
    if fresh_seed is None:
        test = split_people(n_people, split_seed)["test"]
    else:
        test = np.arange(n_people)
    test = test[people.group[test] == PATIENT][:limit]
    people, rules = subset(people, rules, test)

    policies: dict[str, Policy] = {
        "random": RandomZones(np.random.default_rng([seed, 2])),
        "fixed_rule": FixedRule(networks),
        "learned_general": LearnedPolicy(networks, personal=False),
        "learned": LearnedPolicy(networks, personal=True),
        "oracle": Oracle(),
    }
    results = {}
    for name, policy in policies.items():
        rng = np.random.default_rng([seed, 1])  # les mêmes tirages pour toutes les politiques
        state, _, log = simulate_policy(rng, people, rules, l_ref, policy)
        results[name] = _summary(log, state, people.natural)
    return {
        "test_patients": int(len(test)),
        "days": setup["n_days"],
        "population_seed": seed,
        "fresh_people": fresh_seed is not None,
        "policies": results,
    }


def table(report: dict) -> str:
    lines = [
        f"{report['test_patients']} patients de test, {report['days']} jours",
        f"{'Politique':<36}{'Récompense':>11}{'Contre attendu':>16}{'Réponses':>10}"
        f"{'Surcharge':>11}{'Gain état':>11}",
    ]
    for name, row in report["policies"].items():
        lines.append(
            f"{LABELS[name]:<36}{row['reward']:>11.1f}{row['reward_counterfactual']:>16.1f}"
            f"{100 * row['reply_rate']:>9.0f}%{100 * row['overload_rate']:>10.0f}%"
            f"{row['state_lift']:>11.2f}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare B à ses références en boucle fermée.")
    parser.add_argument("--data", type=Path, default=Path("ml/data/sim_big"))
    parser.add_argument("--weights", type=Path, default=Path("ml/weights"))
    parser.add_argument("--limit", type=int, default=None, help="nombre de patients de test")
    parser.add_argument(
        "--fresh",
        type=int,
        default=None,
        metavar="GRAINE",
        help="évaluer sur des personnes entièrement nouvelles, tirées avec cette graine",
    )
    args = parser.parse_args()
    report = evaluate(args.data, args.weights, args.limit, fresh_seed=args.fresh)
    print(table(report))
    name = "evaluation.json" if args.fresh is None else "evaluation_fresh.json"
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    (args.weights / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"Écrit dans {args.weights / name}")


if __name__ == "__main__":
    main()
