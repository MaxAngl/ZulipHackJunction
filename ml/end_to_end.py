"""Rapport de bout en bout sur des patients simulés jamais vus (issue #47).

Usage : uv run python -m ml.end_to_end [--patients 100] [--seed 2026] [--out ml/data/e2e]

Trois parties, dans le même tirage de personnes :

1. Appariement : chaque patient et chaque aidant reçoit des centres d'intérêt, tirés surtout
   dans une « famille » (plein air, cuisine, musique…). On forme les couples comme l'app
   (`ml.matching`, repli hors ligne : aucun appel à Gemini) et on compare à un tirage au hasard.
2. Convergence : les patients vivent `--days` jours avec le réseau B. Pour chaque demande, on
   compare ce que A prédit (récompense, réponse) à ce qui s'est passé, et L(θ) à l'état caché.
3. Bien-être dans le temps : trois patients (sévère, moyen, léger), quatre rythmes d'aide, les
   mêmes tirages. La courbe est la distance à la zone saine, d, réelle (état caché) et mesurée
   (L(θ), ce que l'app voit). Plus d est bas, mieux le patient va.

Tout est simulé : ces chiffres disent si la machinerie fait ce qu'on attend d'elle sur le
simulateur, pas ce qu'elle ferait avec de vrais patients. Les poids viennent de `ml/weights`,
entraînés avec la graine 0 : la graine par défaut ici en est différente.
"""

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # aucun écran : on écrit des fichiers PNG

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from ml.matching import coverage, interest_items, offline_profile, stable_match  # noqa: E402
from ml.nets.features import SLOTS  # noqa: E402
from ml.nets.policy import LearnedPolicy  # noqa: E402
from ml.nets.runtime import Networks  # noqa: E402
from ml.simulation import patient, population, subset  # noqa: E402
from ml.simulation.episodes import Moment, simulate_policy  # noqa: E402
from ml.simulation.people import PATIENT, People, observe  # noqa: E402
from ml.simulation.reward import distance  # noqa: E402
from ml.simulation.spec import (  # noqa: E402
    AXES,
    COMPONENTS,
    CONTEXT_DAYS,
    INTERVAL_AXES,
    REWARD_DELAY_DAYS,
    SIGNALS,
)

FAMILIES = {
    "outdoors": ["hiking", "cycling", "gardening", "birdwatching", "fishing"],
    "food": ["cooking", "baking", "coffee", "wine tasting", "foraging"],
    "music": ["jazz", "guitar", "choir singing", "piano", "vinyl records"],
    "crafts": ["knitting", "woodworking", "painting", "pottery", "sewing"],
    "mind": ["reading", "chess", "board games", "crosswords", "history"],
    "screen": ["photography", "films", "video games", "podcasts", "drawing"],
}
OWN_FAMILY = 0.75  # part des intérêts tirés dans la famille principale de la personne
RHYTHMS = {
    "Aucune demande": None,
    "Tous les 7 jours": 7,
    "Tous les 3 jours": 3,
    "Tous les jours": 1,
}
COLORS = {
    "Aucune demande": "#9ca3af",
    "Tous les 7 jours": "#60a5fa",
    "Tous les 3 jours": "#f59e0b",
    "Tous les jours": "#16a34a",
}


# --- 1. Appariement ----------------------------------------------------------------------------


def draw_interests(rng: np.random.Generator, n: int) -> list[list[str]]:
    """De 2 à 4 intérêts par personne, surtout dans sa famille principale."""
    names = list(FAMILIES)
    people = []
    for _ in range(n):
        home = FAMILIES[names[rng.integers(len(names))]]
        chosen: list[str] = []
        for _ in range(rng.integers(2, 5)):
            pool = home if rng.random() < OWN_FAMILY else FAMILIES[names[rng.integers(len(names))]]
            chosen.append(pool[rng.integers(len(pool))])
        people.append(list(dict.fromkeys(chosen)))
    return people


@dataclass(frozen=True)
class Couple:
    patient: list[str]
    helper: list[str]
    score: float


def quartile_couples(couples: list[Couple]) -> dict[str, Couple]:
    """Le couple dont le score est le plus proche du 1er quartile, de la médiane, du 3e."""
    scores = np.array([couple.score for couple in couples])
    picks = {}
    for label, q in (("1er quartile", 25), ("Médiane", 50), ("3e quartile", 75)):
        target = np.percentile(scores, q)
        picks[label] = couples[int(np.argmin(np.abs(scores - target)))]
    return picks


def matching_part(rng: np.random.Generator, n: int, out: Path) -> tuple[dict, list[str]]:
    patients_tags, helpers_tags = draw_interests(rng, n), draw_interests(rng, n)
    patients = {f"p{i}": offline_profile(interest_items(t)) for i, t in enumerate(patients_tags)}
    helpers = {f"h{i}": offline_profile(interest_items(t)) for i, t in enumerate(helpers_tags)}
    matched = stable_match(patients, helpers, {})

    def couple(p: str, h: str) -> Couple:
        score = coverage(patients[p], helpers[h])
        return Couple(patients_tags[int(p[1:])], helpers_tags[int(h[1:])], score)

    couples = [couple(p, h) for p, h in matched.items()]
    shuffled = rng.permutation(list(helpers))
    random_scores = [
        coverage(patients[p], helpers[h]) for p, h in zip(patients, shuffled, strict=True)
    ]
    best = [max(coverage(patients[p], helpers[h]) for h in helpers) for p in patients]
    scores = np.array([c.score for c in couples])

    figure, axis = plt.subplots(figsize=(7, 4))
    bins = np.linspace(0, 1, 21)
    axis.hist(random_scores, bins=bins, alpha=0.6, label="Couples au hasard", color="#9ca3af")
    axis.hist(scores, bins=bins, alpha=0.7, label="Couples de l'appariement", color="#16a34a")
    axis.set_xlabel("Score de couverture des intérêts du patient (0 à 1)")
    axis.set_ylabel("Nombre de couples")
    axis.set_title(f"Appariement de {n} patients et {n} aidants")
    axis.legend()
    figure.tight_layout()
    figure.savefig(out / "1_appariement.png", dpi=130)
    plt.close(figure)

    summary = {
        "couples": len(couples),
        "score_moyen": float(scores.mean()),
        "score_moyen_hasard": float(np.mean(random_scores)),
        "part_meilleur_aidant": float(np.mean(scores >= np.array(best) - 1e-9)),
        "part_au_moins_un_interet_commun": float(
            np.mean([bool(set(c.patient) & set(c.helper)) for c in couples])
        ),
    }
    lines = [
        "## 1. Appariement",
        "",
        f"- {len(couples)} couples formés, score moyen **{summary['score_moyen']:.2f}** "
        f"contre **{summary['score_moyen_hasard']:.2f}** au hasard.",
        f"- {100 * summary['part_au_moins_un_interet_commun']:.0f} % des couples partagent au "
        "moins un intérêt mot pour mot.",
        f"- {100 * summary['part_meilleur_aidant']:.0f} % des patients ont l'aidant qui leur "
        "convient le mieux à eux seuls (les autres le cèdent à un patient qui en a plus besoin).",
        "",
        "| Couple au | Score | Intérêts du patient | Intérêts de l'aidant |",
        "|---|---|---|---|",
    ]
    for label, c in quartile_couples(couples).items():
        lines.append(
            f"| {label} | {c.score:.2f} | {', '.join(c.patient)} | {', '.join(c.helper)} |"
        )
    lines += ["", "![Appariement](1_appariement.png)", ""]
    return summary, lines


# --- 2. Convergence ----------------------------------------------------------------------------


class RecordingPolicy(LearnedPolicy):
    """Le réseau B, qui note en plus ce que A voyait au moment de chaque demande."""

    def __init__(self, networks: Networks) -> None:
        super().__init__(networks, personal=True)
        self.seen: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None:
        asked = moment.asked
        if moment.day >= CONTEXT_DAYS and self._context is not None and asked.any():
            assert self.vectors is not None
            self.seen.append((self._context[asked], axes[asked], self.vectors[asked].copy()))
        super().feedback(moment, axes, reaction)


def measured_states(networks: Networks, theta: np.ndarray) -> np.ndarray:
    """L(θ) à chaque relevé [n, jours x 4, 6], avec la normale des 14 premiers jours."""
    normal = networks.normal(theta[:, : 14 * SLOTS])
    index = np.arange(theta.shape[1])
    states, _ = networks.states(theta, normal, index)
    return states


def auc(score: np.ndarray, positive: np.ndarray) -> float:
    """Aire sous la courbe ROC : chance qu'une réponse ait un score plus haut qu'un silence."""
    ranks = np.argsort(np.argsort(score)) + 1
    n_pos, n_neg = positive.sum(), (~positive).sum()
    return float((ranks[positive].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def convergence_part(
    networks: Networks, people: People, rules: patient.Rules, l_ref, seed: int, out: Path
) -> tuple[dict, list[str]]:
    policy = RecordingPolicy(networks)
    state, theta, log = simulate_policy(
        np.random.default_rng([seed, 1]), people, rules, l_ref, policy
    )
    context, axes, vectors = (np.concatenate(part) for part in zip(*policy.seen, strict=True))
    predicted = networks.predict(context, axes, vectors)
    reply_chance = networks.reply_chance(context, axes, vectors)

    latent = measured_states(networks, theta)
    at = log.day * SLOTS + log.slot
    on_l = networks.reward(latent[log.person, at], latent[log.person, at + SLOTS])
    truths = {
        "Mesurée sur L (ce que A apprend)": on_l,
        "Réelle, sur l'état caché": log.reward_counterfactual,
    }

    figure, axes_grid = plt.subplots(1, 3, figsize=(15, 4.6))
    stats: dict[str, dict] = {}
    for axis, (label, truth) in zip(axes_grid[:2], truths.items(), strict=True):
        axis.scatter(predicted, truth, s=4, alpha=0.25, color="#2563eb")
        edges = np.percentile(predicted, np.linspace(0, 100, 11))
        bin_of = np.clip(np.digitize(predicted, edges[1:-1]), 0, 9)
        x = [predicted[bin_of == b].mean() for b in range(10)]
        y = [truth[bin_of == b].mean() for b in range(10)]
        axis.plot(x, y, "o-", color="#dc2626", label="Moyenne par dixième de prédiction")
        axis.plot([0, 100], [0, 100], "--", color="#6b7280", label="Prédiction parfaite")
        axis.set_xlim(20, 80)
        axis.set_xlabel("Récompense prédite par A")
        axis.set_ylabel("Récompense observée")
        axis.set_title(label)
        axis.legend(fontsize=8)
        stats[label] = {
            "correlation": float(np.corrcoef(predicted, truth)[0, 1]),
            "rmse": float(np.sqrt(np.mean((predicted - truth) ** 2))),
            "rmse_constante": float(truth.std()),
            "haut_cinquieme": float(truth[predicted >= np.percentile(predicted, 80)].mean()),
            "bas_cinquieme": float(truth[predicted <= np.percentile(predicted, 20)].mean()),
        }

    hidden = np.repeat(state, SLOTS, axis=1)[:, : latent.shape[1]]
    seen = ~np.isnan(theta).all(axis=-1)
    errors = np.sqrt(np.mean((latent[seen] - hidden[seen]) ** 2, axis=0))
    sample = np.random.default_rng(seed).choice(
        seen.sum(), size=min(4000, seen.sum()), replace=False
    )
    axis = axes_grid[2]
    for k, name in enumerate(COMPONENTS):
        axis.scatter(hidden[seen][sample, k], latent[seen][sample, k], s=3, alpha=0.25, label=name)
    axis.plot([0, 1], [0, 1], "--", color="#6b7280")
    axis.set_xlabel("État caché (vérité du simulateur)")
    axis.set_ylabel("L(θ) lu par l'autoencodeur")
    axis.set_title("Autoencodeur : L(θ) contre état caché")
    axis.legend(fontsize=7, markerscale=3)
    figure.tight_layout()
    figure.savefig(out / "2_convergence.png", dpi=130)
    plt.close(figure)

    replied = log.replied.astype(bool)
    summary = {
        "demandes": int(len(log.person)),
        "recompense": stats,
        "reponse_auc": auc(reply_chance, replied),
        "reponse_prevue": float(reply_chance.mean()),
        "reponse_observee": float(replied.mean()),
        "autoencodeur_rmse": {n: float(e) for n, e in zip(COMPONENTS, errors, strict=True)},
    }
    lines = [
        "## 2. Convergence des modèles",
        "",
        f"{summary['demandes']} demandes envoyées par le réseau B à {len(people.group)} patients "
        "jamais vus. Pour chacune, ce que A prédisait au moment de l'envoi, contre ce qui "
        "s'est passé.",
        "",
        "| Récompense | Corrélation | Erreur de A | Erreur d'une constante "
        "| Réelle, cinquième préféré par A | Réelle, cinquième déconseillé |",
        "|---|---|---|---|---|---|",
    ]
    for label, s in stats.items():
        lines.append(
            f"| {label} | {s['correlation']:.2f} | {s['rmse']:.1f} | {s['rmse_constante']:.1f} "
            f"| {s['haut_cinquieme']:.1f} | {s['bas_cinquieme']:.1f} |"
        )
    lines += [
        "",
        f"- **Réponse du patient** : AUC {summary['reponse_auc']:.2f} (0,5 = hasard, 1 = parfait). "
        f"Taux prévu {100 * summary['reponse_prevue']:.0f} %, observé "
        f"{100 * summary['reponse_observee']:.0f} %.",
        "- **Autoencodeur**, erreur entre L(θ) et l'état caché (0 à 1) : "
        + ", ".join(f"{n} {e:.3f}" for n, e in summary["autoencodeur_rmse"].items())
        + f" ; moyenne {float(errors.mean()):.3f}.",
        "",
        "![Convergence](2_convergence.png)",
        "",
    ]
    return summary, lines


# --- 3. Bien-être dans le temps ----------------------------------------------------------------


def schedule(n_days: int, every: int | None) -> np.ndarray:
    """Les jours où le patient reçoit une demande : jamais pendant la semaine de contexte."""
    days = np.arange(n_days)
    if every is None:
        return np.zeros(n_days, dtype=bool)
    return (days >= CONTEXT_DAYS) & ((days - CONTEXT_DAYS) % every == 0)


def live_with_rhythm(
    networks: Networks, people: People, rules: patient.Rules, every: int | None, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """La boucle de `simulate_policy`, mais les demandes suivent un rythme fixe.

    Les tirages aléatoires sont consommés exactement de la même façon quel que soit le rythme :
    seul le rythme change d'un scénario à l'autre. Renvoie l'état caché [n, jours, 6], les
    relevés θ et les jours de demande.
    """
    rng = np.random.default_rng([seed, 3])
    policy = LearnedPolicy(networks, personal=True)
    natural = people.natural
    n_people, n_days, _ = natural.shape
    asked_days = schedule(n_days, every)
    state = natural.copy()
    boost = np.zeros((n_people, natural.shape[2]))
    theta = np.full((n_people, n_days * SLOTS, len(SIGNALS)), np.nan, dtype=np.float32)
    for day in range(n_days):
        state[:, day] = np.clip(natural[:, day] + boost, 0.0, 1.0)
        theta[:, day * SLOTS : (day + 1) * SLOTS] = observe(rng, people, state[:, day : day + 1])
        if day >= n_days - REWARD_DELAY_DAYS:
            break
        rng.random(n_people)  # le tirage « demande ou pas » de simulate_policy, ici ignoré
        asked = np.full(n_people, asked_days[day])
        slot = rng.integers(0, SLOTS, n_people)
        moment = Moment(day, slot, theta, asked, state[:, day], rules)
        low, high, startup = (np.clip(v, 0.0, 1.0) for v in policy.zones(moment))
        axes = np.empty((n_people, len(AXES)))
        axes[:, :INTERVAL_AXES] = low + rng.random(low.shape) * (high - low)
        axes[:, INTERVAL_AXES] = rng.random(n_people) * startup
        reaction = patient.react(rng, rules, state[:, day], axes, people.traits["chattiness"])
        policy.feedback(moment, axes, reaction)
        boost = patient.EFFECT_DECAY * boost + np.where(asked[:, None], reaction.effect, 0.0)
    return state, theta, asked_days


def wellbeing_part(
    networks: Networks, people: People, rules: patient.Rules, l_ref, seed: int, out: Path
) -> tuple[dict, list[str]]:
    severity = distance(people.natural, *l_ref).mean(axis=1)
    order = np.argsort(severity)
    chosen = {
        "Patient sévère": order[int(0.9 * (len(order) - 1))],
        "Patient moyen": order[len(order) // 2],
        "Patient léger": order[int(0.1 * (len(order) - 1))],
    }
    trio_people, trio_rules = subset(people, rules, np.array(list(chosen.values())))
    days = np.arange(people.natural.shape[1])

    curves = {}
    for rhythm, every in RHYTHMS.items():
        state, theta, asked_days = live_with_rhythm(networks, trio_people, trio_rules, every, seed)
        latent = measured_states(networks, theta).reshape(len(chosen), len(days), SLOTS, -1)
        real = distance(state, *l_ref)
        seen = networks.distance(np.nanmean(latent, axis=2))
        curves[rhythm] = (real, seen, asked_days)

    summary: dict[str, dict] = {}
    lines = [
        "## 3. Bien-être dans le temps",
        "",
        "Ordonnée : la distance à la zone saine, d. Une personne saine typique est autour de 1. "
        "**L'axe est retourné : plus la courbe monte, mieux le patient va.** En haut, l'état "
        "réel (caché, la vérité du simulateur) ; en bas, l'état mesuré L(θ), ce que l'app voit. "
        "Chaque trait vertical en bas d'un graphe est une demande. Mêmes tirages pour les "
        "quatre rythmes : seule l'aide change.",
        "",
        "| Patient | Rythme | d réel, 4 dernières semaines | d mesuré, 4 dernières semaines |",
        "|---|---|---|---|",
    ]
    for k, (name, _) in enumerate(chosen.items()):
        figure, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        summary[name] = {}
        for rhythm, (real, seen, asked_days) in curves.items():
            color = COLORS[rhythm]
            top.plot(days, real[k], color=color, label=rhythm, linewidth=1.8)
            bottom.plot(days, seen[k], color=color, label=rhythm, linewidth=1.4)
            if rhythm != "Aucune demande":
                # Une ligne de traits par rythme, sous le graphe : un trait = une demande.
                level = list(RHYTHMS).index(rhythm)
                for axis in (top, bottom):
                    axis.eventplot(
                        days[asked_days],
                        lineoffsets=-0.03 - 0.035 * level,
                        linelengths=0.03,
                        colors=color,
                        transform=axis.get_xaxis_transform(),
                        clip_on=False,
                    )
            last = slice(-28, None)
            row = {"reel": float(real[k, last].mean()), "mesure": float(np.nanmean(seen[k, last]))}
            summary[name][rhythm] = row
            lines.append(f"| {name} | {rhythm} | {row['reel']:.2f} | {row['mesure']:.2f} |")
        for axis, title in (
            (top, "État réel (caché)"),
            (bottom, "État mesuré L(θ), ce que l'app voit"),
        ):
            axis.axhline(1.0, color="#6b7280", linestyle="--", linewidth=1)
            axis.text(days[-1], 1.0, " personne saine typique", va="bottom", ha="right", fontsize=8)
            axis.axvspan(0, CONTEXT_DAYS - 0.5, color="#f3f4f6")
            axis.invert_yaxis()
            axis.set_ylabel("Distance à la zone saine d\n(↑ = va mieux)")
            axis.set_title(title, fontsize=10)
        bottom.set_xlabel(
            "Jour (la première semaine, en gris, sert de contexte : aucune demande)", labelpad=34
        )
        figure.legend(
            *top.get_legend_handles_labels(), loc="upper center", ncol=4, fontsize=9,
            bbox_to_anchor=(0.5, 0.95), frameon=False,
        )  # fmt: skip
        figure.suptitle(f"{name} : bien-être selon le rythme d'aide", y=0.99)
        figure.subplots_adjust(top=0.86, hspace=0.42)
        file = f"3_bien_etre_{k + 1}.png"
        figure.savefig(out / file, dpi=130, bbox_inches="tight")
        plt.close(figure)
        lines += ["", f"![{name}]({file})", ""]
    return summary, lines


# --- Tout enchaîner ----------------------------------------------------------------------------


def run(n_patients: int, n_days: int, seed: int, weights: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    networks = Networks.load(weights)
    healthy_share = 0.4
    n_people = math.ceil(1.3 * n_patients / (1 - healthy_share))
    _, people, rules, l_ref = population(n_people, n_days, healthy_share, seed)
    patients = np.flatnonzero(people.group == PATIENT)[:n_patients]
    if len(patients) < n_patients:
        raise ValueError("Pas assez de patients tirés : augmenter la marge.")
    people, rules = subset(people, rules, patients)

    header = [
        "# Rapport de bout en bout",
        "",
        f"{n_patients} patients simulés jamais vus (graine {seed}), {n_days} jours, poids de "
        f"`{weights.as_posix()}`. Tout est simulé : ces chiffres disent si la machinerie fait ce "
        "qu'on attend d'elle sur le simulateur, pas ce qu'elle ferait avec de vrais patients.",
        "",
    ]
    rng = np.random.default_rng([seed, 4])
    matching, part1 = matching_part(rng, n_patients, out)
    convergence, part2 = convergence_part(networks, people, rules, l_ref, seed, out)
    wellbeing, part3 = wellbeing_part(networks, people, rules, l_ref, seed, out)
    text = "\n".join(header + part1 + part2 + part3) + "\n"
    (out / "rapport.md").write_text(text, encoding="utf-8", newline="\n")
    return {"appariement": matching, "convergence": convergence, "bien_etre": wellbeing}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rapport de bout en bout sur patients simulés.")
    parser.add_argument("--patients", type=int, default=100)
    parser.add_argument("--days", type=int, default=84)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--weights", type=Path, default=Path("ml/weights"))
    parser.add_argument("--out", type=Path, default=Path("ml/data/e2e"))
    args = parser.parse_args()
    run(args.patients, args.days, args.seed, args.weights, args.out)
    print(f"Rapport écrit dans {args.out / 'rapport.md'}")


if __name__ == "__main__":
    main()
