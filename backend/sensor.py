"""Capteur d'état SIMULÉ.

Hypothèse de l'équipe : l'état θ du patient se mesure sans rien lui demander, à tout instant, et
son comportement (il répond ou non, il va au bout ou non) fait partie de θ. Tant qu'aucun vrai
capteur n'est branché, ce module joue ce rôle pour la démo.

Le patient simulé a une préférence cachée que le modèle ne connaît pas : il réagit mieux à des
demandes un peu plus proches des intérêts de l'aidant que ne le prévoit la règle commune.
C'est ce que la boucle doit découvrir. La simulation est déterministe : même action, même effet.
"""

from ml.model import common_center, effort_cap

TRUE_OFFSET = -0.12  # écart caché entre le goût réel de ce patient et la règle commune
SWEET_RADIUS = 0.25  # au-delà de cette distance au point idéal, la demande n'apporte presque rien
GAIN_BASE = 0.01
GAIN_FIT = 0.06
LOSS_IGNORED = 0.04
STRAIN_COST = 0.10

# Sans demande, l'état revient lentement vers son niveau de repos.
RESTING_THETA = 0.55
REVERSION = 0.10


def _clamp(value: float, low: float = 0.02, high: float = 0.98) -> float:
    return max(low, min(high, value))


def expected_theta(theta_before: float) -> float:
    """Ce que θ aurait été sans la demande, sur la fenêtre de mesure."""
    return _clamp(theta_before + REVERSION * (RESTING_THETA - theta_before))


def theta_after(theta_before: float, lam: float, effort: float, helped: bool) -> float:
    """État mesuré après la demande, réaction du patient comprise."""
    expected = expected_theta(theta_before)
    if not helped:
        return _clamp(expected - LOSS_IGNORED)
    sweet_spot = common_center(theta_before) + TRUE_OFFSET
    fit = max(0.0, 1.0 - abs(lam - sweet_spot) / SWEET_RADIUS)
    strain = max(0.0, effort - effort_cap(theta_before))
    return _clamp(expected + GAIN_BASE + GAIN_FIT * fit - STRAIN_COST * strain)
