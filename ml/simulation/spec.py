"""Le vocabulaire des données simulées : signaux de θ, composantes de l'état, axes d'une demande.

θ réunit ce qu'une montre Garmin Forerunner 965 mesure d'utile pour suivre une personne, plus
son comportement dans l'app. Un relevé de θ est pris à un instant : les signaux de la nuit et du
jour y figurent avec leur dernière valeur connue.
"""

from dataclasses import dataclass

# Quatre relevés par jour. La séquence donnée au réseau B couvre sept jours, soit 28 relevés.
SNAPSHOT_HOURS: tuple[int, ...] = (8, 13, 18, 22)
CONTEXT_DAYS = 7
CONTEXT_LENGTH = CONTEXT_DAYS * len(SNAPSHOT_HOURS)

# Délai entre une demande et la nouvelle mesure : 24 heures, au même moment de la journée.
REWARD_DELAY_DAYS = 1

# Les six composantes de l'état caché, que L(θ) devra retrouver. Chacune va de 0 à 1,
# et plus elle est haute, mieux la personne va.
COMPONENTS: tuple[str, ...] = ("sleep", "rhythm", "energy", "calm", "activity", "engagement")

# Les six axes de la phase 1 (docs/modele.md, section 3). Les cinq premiers reçoivent un
# intervalle dans la zone, le dernier un plafond seul.
AXES: tuple[str, ...] = ("interest", "concrete", "duration", "exchange", "exposure", "startup")
INTERVAL_AXES = 5


# Une modalité est une source de données : la montre, les réponses dans l'app, la frappe.
# Chaque bloc de signaux appartient à une modalité. L'autoencodeur a un encodeur par modalité :
# en ajouter une ne touche ni aux autres encodeurs, ni aux réseaux A et B, qui ne lisent que L.
MODALITY_OF_BLOCK: dict[str, str] = {
    "instant": "watch",
    "day": "watch",
    "night": "watch",
    "daily": "watch",
    "app": "app",
    "touch": "touch",
}
MODALITIES: tuple[str, ...] = ("watch", "app", "touch")


@dataclass(frozen=True)
class Signal:
    name: str
    unit: str
    block: str  # instant, day, night, daily, app ou touch
    component: str  # la composante de l'état qui pèse le plus sur ce signal
    low: float  # bornes plausibles : toute valeur générée y est ramenée
    high: float
    log: bool = False  # signal très étalé : les réseaux en lisent le logarithme

    @property
    def modality(self) -> str:
        return MODALITY_OF_BLOCK[self.block]


SIGNALS: tuple[Signal, ...] = (
    # Mesures instantanées, moyennées sur la demi-heure qui précède le relevé.
    Signal("heart_rate", "bpm", "instant", "calm", 38, 190),
    Signal("stress", "0-100", "instant", "calm", 0, 100),
    Signal("body_battery", "0-100", "instant", "energy", 5, 100),
    Signal("respiration", "resp/min", "instant", "calm", 8, 28),
    Signal("steps_last_hour", "pas", "instant", "activity", 0, 9000, log=True),
    # Cumuls de la journée, à l'heure du relevé.
    Signal("steps_today", "pas", "day", "activity", 0, 40000, log=True),
    Signal("intensity_minutes_today", "min", "day", "activity", 0, 300),
    Signal("floors_today", "étages", "day", "activity", 0, 80),
    Signal("outdoor_minutes_today", "min", "day", "activity", 0, 480),
    # Dernière nuit.
    Signal("sleep_hours", "h", "night", "sleep", 1, 14),
    Signal("sleep_score", "0-100", "night", "sleep", 0, 100),
    Signal("deep_sleep_minutes", "min", "night", "sleep", 0, 200),
    Signal("rem_sleep_minutes", "min", "night", "sleep", 0, 240),
    Signal("awake_minutes", "min", "night", "sleep", 0, 240),
    Signal("bedtime_hour", "h (après midi)", "night", "rhythm", 6, 20),
    Signal("wake_hour", "h", "night", "rhythm", 2, 16),
    Signal("hrv_overnight_ms", "ms", "night", "calm", 8, 180),
    Signal("spo2_sleep", "%", "night", "sleep", 85, 100),
    # Valeur du jour.
    Signal("resting_hr", "bpm", "daily", "energy", 35, 110),
    # Comportement dans l'app, sur les sept derniers jours.
    Signal("reply_rate_7d", "0-1", "app", "engagement", 0, 1),
    Signal("reply_delay_hours_7d", "h", "app", "engagement", 0.1, 48),
    Signal("reply_length_7d", "caractères", "app", "engagement", 5, 600),
    # Frappe et réactivité, relevées la dernière fois que la personne a écrit dans l'app.
    # On ne garde que des durées et des comptes, jamais les caractères tapés.
    Signal("typing_correction_rate", "pour 100 caractères", "touch", "sleep", 0, 60, log=True),
    Signal("open_delay_minutes", "min", "touch", "engagement", 0.2, 720, log=True),
    Signal("first_key_delay_seconds", "s", "touch", "energy", 0.5, 300, log=True),
)

SIGNAL_NAMES: tuple[str, ...] = tuple(signal.name for signal in SIGNALS)


def signal_index(name: str) -> int:
    return SIGNAL_NAMES.index(name)


def modality_indices() -> dict[str, list[int]]:
    """Pour chaque modalité, les colonnes de θ qui lui appartiennent."""
    return {
        modality: [index for index, signal in enumerate(SIGNALS) if signal.modality == modality]
        for modality in MODALITIES
    }


def component_index(name: str) -> int:
    return COMPONENTS.index(name)
