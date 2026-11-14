"""Point d'entrée du module ML.

CONTRAT avec backend/ : le backend n'importe que depuis ce fichier. Les signatures et les
types exportés ici (voir `__all__`) ne changent pas sans prévenir l'équipe (voir AGENTS.md).
L'intérieur se change librement.

LA ZONE VIENT DES RÉSEAUX ENTRAÎNÉS. `brain()` charge les poids de `ml/weights` et rend un
`Brain` : il lit l'état L(θ) (autoencodeur), sort la zone sur six axes (réseau B, seul), note une
demande après coup et règle le vecteur personnel du patient (à travers le réseau A). Ces réseaux
sont entraînés sur des données simulées (docs/modele.md, section 14).

`VirtualPatient` tient lieu de montre : il produit les 25 signaux de θ. C'est la seule partie
encore simulée de la boucle.

`zone_for` et `learn` sont l'ancienne règle écrite à la main, à un seul nombre. Elles ne servent
plus à l'app : elles restent comme point de comparaison (`ml.nets.policy.FixedRule`).
"""

import math
import os
from pathlib import Path

from ml.brain import COMPONENT_LABELS, Brain, Outcome, Reading, brain
from ml.formats import FORMATS, RequestFormat, request_axes
from ml.formats import label_of as format_label
from ml.matching import InterestProfile, build_profile, stable_match
from ml.pipeline import generate_candidates, measure_message, provider_info, select_three
from ml.simulation.spec import SIGNALS
from ml.types import (
    AXIS_KEYS,
    AXIS_LABELS,
    Candidate,
    InterestPair,
    Provider,
    ProviderInfo,
    Review,
    Slot,
    Zone,
    ZoneBox,
    ZoneParams,
)
from ml.virtual import VirtualPatient
from ml.watch import theta_from_watch

__all__ = [
    "AXIS_KEYS",
    "AXIS_LABELS",
    "COMPONENT_LABELS",
    "FORMATS",
    "SIGNALS",
    "Brain",
    "Candidate",
    "InterestPair",
    "InterestProfile",
    "Outcome",
    "Provider",
    "ProviderInfo",
    "Reading",
    "RequestFormat",
    "Review",
    "Slot",
    "VirtualPatient",
    "Zone",
    "ZoneBox",
    "ZoneParams",
    "brain",
    "build_profile",
    "common_center",
    "effort_cap",
    "format_label",
    "generate_candidates",
    "learn",
    "load_env_file",
    "measure_message",
    "provider_info",
    "request_axes",
    "select_three",
    "stable_match",
    "theta_from_watch",
    "zone_for",
]

# Règle de départ (modèle commun) : plus le patient va mal, plus la zone se rapproche de ses
# propres centres d'intérêt et plus la demande doit être légère.
LAMBDA_SLOPE = 0.6  # centre = 1 − 0,6·θ
EFFORT_FLOOR = 0.25  # plafond d'effort = 0,25 + 0,75·θ

# Largeur de la zone = incertitude : large pour un nouveau patient, elle se resserre.
WIDTH_START = 0.18
WIDTH_MIN = 0.07

# Faux apprentissage par patient.
OFFSET_LIMIT = 0.3
LEARNING_RATE = 0.6
REWARD_BASELINE = 0.04  # gain d'état habituel après une demande rendue
REWARD_SCALE = 0.03


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def common_center(theta: float) -> float:
    """Centre de la zone donné par le modèle commun, pour un état θ entre 0 et 1."""
    return _clamp(1.0 - LAMBDA_SLOPE * _clamp(theta))


def effort_cap(theta: float) -> float:
    """Effort maximal acceptable pour un état θ."""
    return _clamp(EFFORT_FLOOR + (1.0 - EFFORT_FLOOR) * _clamp(theta))


def zone_for(theta: float, params: ZoneParams | None = None) -> Zone:
    """Étape 2 de la boucle : la zone d'un patient = zone commune + correction personnelle."""
    params = params or ZoneParams()
    shared = common_center(theta)
    half_width = max(WIDTH_MIN, WIDTH_START / math.sqrt(1.0 + params.n_obs / 2.0))
    return Zone(
        center=_clamp(shared + params.offset),
        half_width=half_width,
        effort_max=effort_cap(theta),
        common_center=shared,
    )


def learn(params: ZoneParams, theta: float, lam_sent: float, reward: float) -> ZoneParams:
    """Étape 12 : met à jour la correction personnelle après une réponse du patient.

    SIMULÉ : si la demande a fait mieux que d'habitude, le centre se déplace vers sa position ;
    si elle a fait moins bien, il s'en éloigne. `reward` = θ après − θ attendu.
    """
    center = zone_for(theta, params).center
    signal = _clamp((reward - REWARD_BASELINE) / REWARD_SCALE, -1.0, 1.0)
    offset = params.offset + LEARNING_RATE * signal * (lam_sent - center)
    return ZoneParams(offset=_clamp(offset, -OFFSET_LIMIT, OFFSET_LIMIT), n_obs=params.n_obs + 1)


def load_env_file(path: Path | None = None) -> None:
    """Charge `.env` (clé Gemini) sans écraser les variables déjà définies."""
    env_path = path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        entry = line.strip().removeprefix("export ").strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        value = value.strip().strip("\"'")
        if key.strip() and value:
            os.environ.setdefault(key.strip(), value)
