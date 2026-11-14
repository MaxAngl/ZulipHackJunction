"""Types partagés du module ML. Ils sont ré-exportés par ml/model.py, qui est le contrat."""

from dataclasses import dataclass
from typing import Literal

Provider = Literal["claude", "gemini", "offline"]
Slot = Literal["best", "bridge", "explore"]


# Les six axes d'une demande (docs/modele.md, section 3), dans l'ordre des réseaux.
AXIS_KEYS: tuple[str, ...] = ("interest", "concrete", "duration", "exchange", "exposure", "startup")
AXIS_LABELS: dict[str, str] = {
    "interest": "Interests",
    "concrete": "Concrete",
    "duration": "Duration",
    "exchange": "Human exchange",
    "exposure": "Personal exposure",
    "startup": "Start-up cost",
}
_TOLERANCE = 1e-9


@dataclass(frozen=True)
class ZoneBox:
    """La zone sur les six axes, telle que le réseau B la sort.

    Un intervalle pour les cinq premiers axes (intérêts, concret, durée, échange, exposition),
    un plafond seul pour le coût de démarrage.
    """

    low: tuple[float, ...]  # 5 bornes basses
    high: tuple[float, ...]  # 5 bornes hautes
    startup_max: float

    def allows_costs(self, format_axes: tuple[float, ...]) -> bool:
        """Les bornes hautes des axes de coût sont une sécurité : jamais dépassées.

        `format_axes` : concret, durée, échange, exposition, démarrage. L'axe concret n'est pas
        un coût : il ne bloque rien.
        """
        costs_fit = all(
            value <= ceiling + _TOLERANCE
            for value, ceiling in zip(format_axes[1:4], self.high[2:5], strict=True)
        )
        return costs_fit and format_axes[4] <= self.startup_max + _TOLERANCE

    def allows(self, axes: tuple[float, ...]) -> bool:
        """Une demande entre dans la zone : bien placée entre les intérêts, et pas trop lourde."""
        inside = self.low[0] - _TOLERANCE <= axes[0] <= self.high[0] + _TOLERANCE
        return inside and self.allows_costs(tuple(axes[1:]))

    def shortfall(self, axes: tuple[float, ...]) -> float:
        """De combien une demande s'écarte de ce que la zone vise, hors sécurité.

        Les bornes basses sont un objectif, pas une obligation : une demande trop légère, ou
        plus concrète que visé, reste permise. Cet écart sert seulement à choisir entre des
        demandes permises.
        """
        gap = 0.0
        for value, low, high in zip(axes[1:5], self.low[1:], self.high[1:], strict=True):
            gap += max(0.0, low - value) + max(0.0, value - high)
        return gap


@dataclass(frozen=True)
class Zone:
    """Zone des demandes acceptables pour un patient, à un instant donné.

    `center` et `half_width` sont sur l'axe λ (0 = intérêts de l'aidant, 1 = intérêts du patient).
    `common_center` est le centre donné par le modèle commun, avant correction personnelle.
    `box` est la zone complète sur les six axes quand elle vient du réseau B ; sans elle, c'est
    l'ancienne règle à deux axes, où `effort_max` plafonne l'effort du format.
    """

    center: float
    half_width: float
    effort_max: float
    common_center: float
    box: ZoneBox | None = None

    @property
    def low(self) -> float:
        return max(0.0, self.center - self.half_width)

    @property
    def high(self) -> float:
        return min(1.0, self.center + self.half_width)

    def contains(self, lam: float, effort: float, axes: tuple[float, ...] | None = None) -> bool:
        """Une demande entre-t-elle dans la zone ? Avec `axes` et une zone à six axes, la
        réponse vient des six axes ; sinon de la position et de l'effort du format."""
        if self.box is not None and axes is not None:
            return self.box.allows(tuple(axes))
        return self.low <= lam <= self.high and effort <= self.effort_max + 1e-9

    def shortfall(self, lam: float, axes: tuple[float, ...] | None = None) -> float:
        """Écart au cœur de la zone : sert à ranger les demandes permises, la meilleure d'abord."""
        gap = abs(lam - self.center)
        if self.box is not None and axes is not None:
            gap += self.box.shortfall(tuple(axes))
        return gap


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
    axes: tuple[float, ...] | None = None  # position sur les six axes (ml.formats.request_axes)


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
