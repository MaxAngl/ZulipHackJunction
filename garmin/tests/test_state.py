"""État provisoire : il suit l'état de la montre simulée et ignore ce qu'il ne sait pas lire."""

import pytest

from garmin.__main__ import main
from garmin.simulated import simulated_reading
from ml.watch import RULES, estimate


def centered_reading() -> dict[str, float]:
    """Relevé d'une personne moyenne dont toutes les composantes valent 0,5, en fin de journée."""
    reading = {name: rule.center for name, rule in RULES.items()}
    reading["body_battery"] = RULES["body_battery"].center - 1.1 * 34.0  # vidé à 22 h
    return reading


def test_average_person_sits_in_the_middle() -> None:
    result = estimate(centered_reading(), hour=22.0)

    assert set(result.components) == {"sleep", "energy", "calm", "activity"}
    assert result.theta == pytest.approx(0.5, abs=0.01)


def test_better_night_raises_the_state() -> None:
    better = centered_reading() | {"sleep_score": 90.0, "sleep_hours": 8.2, "awake_minutes": 10.0}

    assert estimate(better, hour=22.0).theta > estimate(centered_reading(), hour=22.0).theta


def test_day_totals_are_ignored_early_in_the_morning() -> None:
    only_totals = {"steps_today": 300.0, "floors_today": 1.0}

    with pytest.raises(ValueError):
        estimate(only_totals, hour=7.0)


def test_empty_reading_is_refused() -> None:
    with pytest.raises(ValueError):
        estimate({}, hour=13.0)


def test_follows_the_simulated_patient() -> None:
    def mean_theta(level: float) -> float:
        thetas = [estimate(simulated_reading(18.0, level, seed), 18.0).theta for seed in range(20)]
        return sum(thetas) / len(thetas)

    low, high = mean_theta(0.2), mean_theta(0.85)

    assert low < 0.4 < 0.6 < high


def test_command_runs_with_the_simulated_watch(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["read", "--simulate", "--level", "0.5", "--seed", "1"]) == 0
    assert "θ provisoire" in capsys.readouterr().out
