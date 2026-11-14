"""Patient virtuel : de vraies mesures remplacent celles du simulateur dans θ."""

import numpy as np

from ml.simulation.spec import signal_index
from ml.virtual import VirtualPatient


def test_real_measurements_replace_simulated_ones() -> None:
    body = VirtualPatient(seed=7)
    before = body.theta.copy()
    measured = (signal_index("heart_rate"), signal_index("hrv_overnight_ms"))

    body.measure({"heart_rate": 77.0, "hrv_overnight_ms": 86.0})

    assert body.theta[-1, measured[0]] == 77.0
    assert body.theta[-1, measured[1]] == 86.0
    others = [i for i in range(before.shape[1]) if i not in measured]
    assert np.array_equal(body.theta[-1, others], before[-1, others], equal_nan=True)
    assert np.array_equal(body.theta[:-1], before[:-1], equal_nan=True)  # le passé ne bouge pas


def test_last_known_value_carries_into_the_next_days() -> None:
    body = VirtualPatient(seed=7)

    body.measure({"resting_hr": 52.0})
    body.rest()

    assert np.all(body.theta[-4:, signal_index("resting_hr")] == 52.0)


def test_values_are_kept_within_signal_bounds() -> None:
    body = VirtualPatient(seed=7)

    body.measure({"stress": 250.0})

    assert body.theta[-1, signal_index("stress")] == 100.0
