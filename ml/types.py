"""Types partagés du module ML. Ils sont ré-exportés par ml/model.py, qui est le contrat."""

from dataclasses import dataclass
from typing import Literal

Provider = Literal["gemini", "offline"]
Slot = Literal["best", "bridge", "explore"]


@dataclass(frozen=True)
class Zone:
    """Zone des demandes acceptables pour un patient, à un instant donné.

    `center` et `half_width` sont sur l'axe λ (0 = intérêts de l'aidant, 1 = intérêts du patient).
    `common_center` est le centre donné par le modèle commun, avant correction personnelle.
    """

    center: float
    half_width: float
    effort_max: float
    common_center: float

    @property
    def low(self) -> float:
        return max(0.0, self.center - self.half_width)

    @property
    def high(self) -> float:
        return min(1.0, self.center + self.half_width)

    def contains(self, lam: float, effort: float) -> bool:
        return self.low <= lam <= self.high and effort <= self.effort_max + 1e-9


@dataclass(frozen=True)
class ZoneParams:
    """Correction personnelle du patient : part de zéro, donc de la zone commune."""

    offset: float = 0.0
    n_obs: int = 0


@dataclass(frozen=True)
class InterestPair:
    patient_interest: str
    helper_interest: str


@dataclass(frozen=True)
class Candidate:
    """Une demande mesurée : position λ sur l'axe, format et effort."""

    id: str
    text: str
    pair: InterestPair
    lam: float
    format: str
    effort: float
    off_topic: bool
    provider: Provider
    intended: float | None = None  # position visée par le générateur, quand il la donne


@dataclass(frozen=True)
class Review:
    """Résultat de la relecture d'un message écrit ou modifié par l'aidant."""

    format: str
    effort: float
    safe: bool
    reason: str


@dataclass(frozen=True)
class ProviderInfo:
    provider: Provider
    model: str | None
    note: str
