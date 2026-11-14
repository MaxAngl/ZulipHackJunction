"""Traduit ce que rendent les réseaux vers le contrat d'API, pour la console et la vraie app."""

import math

import numpy as np

from backend import schemas
from ml.model import AXIS_KEYS, AXIS_LABELS, SIGNALS, Brain, Reading, Zone


def zone_state(zone: Zone) -> schemas.ZoneState:
    axes: list[schemas.AxisState] = []
    if zone.box is not None:
        bounds = zip(AXIS_KEYS[:-1], zone.box.low, zone.box.high, strict=True)
        axes = [
            schemas.AxisState(key=key, label=AXIS_LABELS[key], low=low, high=high, kind="interval")
            for key, low, high in bounds
        ]
        last = AXIS_KEYS[-1]
        axes.append(
            schemas.AxisState(
                key=last,
                label=AXIS_LABELS[last],
                low=0.0,
                high=zone.box.startup_max,
                kind="ceiling",
            )
        )
    return schemas.ZoneState(
        center=round(zone.center, 3),
        low=round(zone.low, 3),
        high=round(zone.high, 3),
        half_width=round(zone.half_width, 3),
        effort_max=round(zone.effort_max, 3),
        common_center=round(zone.common_center, 3),
        axes=axes,
    )


def component_states(brain: Brain, reading: Reading) -> list[schemas.ComponentState]:
    return [
        schemas.ComponentState(
            key=key, label=label, value=round(value, 3), reference=round(healthy, 3)
        )
        for key, label, value, healthy in brain.components(reading)
    ]


def signal_states(snapshot: np.ndarray) -> list[schemas.SignalState]:
    """Les signaux bruts d'un relevé de θ. Une donnée absente (NaN) devient `null`."""
    return [
        schemas.SignalState(
            name=signal.name,
            unit=signal.unit,
            modality=signal.modality,
            value=None if math.isnan(value) else round(float(value), 2),
        )
        for signal, value in zip(SIGNALS, snapshot, strict=True)
    ]


def measured_typing(typing: schemas.TypingSignals | None) -> dict[str, float] | None:
    """Les signaux de frappe relevés par l'app, dans les unités de θ."""
    if typing is None:
        return None
    measured: dict[str, float] = {}
    if typing.characters > 0:
        measured["typing_correction_rate"] = 100.0 * typing.corrections / typing.characters
    if typing.open_delay_seconds is not None:
        measured["open_delay_minutes"] = typing.open_delay_seconds / 60.0
    if typing.first_key_delay_seconds is not None:
        measured["first_key_delay_seconds"] = typing.first_key_delay_seconds
    return measured or None


def hold_reason(lam: float, axes: tuple[float, ...] | None, off_topic: bool, zone: Zone) -> str:
    """Pourquoi une demande est retenue. Affiché dans la console, jamais à l'aidant."""
    if off_topic:
        return "Not linked to the patient's interests."
    if lam < zone.low or lam > zone.high:
        side = "below" if lam < zone.low else "above"
        return f"Position {lam:.2f} is {side} the zone ({zone.low:.2f} to {zone.high:.2f})."
    if zone.box is not None and axes is not None:
        ceilings = (*zone.box.high[2:], zone.box.startup_max)
        for key, value, ceiling in zip(AXIS_KEYS[2:], axes[2:], ceilings, strict=True):
            if value > ceiling:
                return f"{AXIS_LABELS[key]} {value:.2f} is above the ceiling {ceiling:.2f}."
    return f"Too demanding for now (effort ceiling {zone.effort_max:.2f})."
