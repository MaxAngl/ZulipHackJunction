"""Contrat ml/ -> backend/ : ce que le backend attend de `predict`."""

from ml.model import Prediction, predict


def test_predict_returns_a_prediction():
    result = predict("super projet")
    assert isinstance(result, Prediction)
    assert isinstance(result.label, str)
    assert 0.0 <= result.score <= 1.0


def test_predict_accepts_empty_text():
    result = predict("")
    assert 0.0 <= result.score <= 1.0
