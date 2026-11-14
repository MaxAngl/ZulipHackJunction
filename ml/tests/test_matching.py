"""Appariement patient–aidant : profils d'intérêts, score de couverture, mariages stables.

Gemini est coupé (`conftest.py`) : les profils viennent du repli hors ligne, sauf quand un test
remplace lui-même `ml.gemini.embed`.
"""

import pytest

from ml import gemini
from ml.matching import (
    WAIT_FULL_DAYS,
    InterestProfile,
    build_profile,
    coverage,
    interest_items,
    stable_match,
)

WEEK = WAIT_FULL_DAYS * 86_400


def test_tags_and_each_sentence_of_the_comment_are_items():
    items = interest_items(["Gardening", " ski "], "I play chess. Jazz on Sundays!\nski")
    assert items == ["gardening", "ski", "i play chess", "jazz on sundays"]


def test_without_gemini_the_profile_is_built_offline():
    profile = build_profile(["gardening"])
    assert profile.provider == "offline"
    assert profile.items == ("gardening",)


def test_with_gemini_the_profile_uses_its_vectors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gemini, "embed", lambda texts: [[3.0, 4.0] for _ in texts])
    profile = build_profile(["gardening"])
    assert profile.provider.startswith("gemini:")
    assert profile.vectors == ((0.6, 0.8),)  # ramené à une norme de 1


def test_everything_is_compared_with_everything():
    """Le ski en commentaire chez l'un retrouve le ski en tag chez l'autre."""
    patient = build_profile(["ski"], "Gardening")
    helper = build_profile(["gardening"], "Ski")
    assert coverage(patient, helper) == pytest.approx(1.0)


def test_only_the_patient_interests_need_to_be_covered():
    patient = build_profile(["ski", "gardening"])
    focused = build_profile(["ski", "gardening"])
    broad = build_profile(["ski", "gardening", "jazz", "chess", "cooking", "photography"])
    assert coverage(patient, broad) == pytest.approx(coverage(patient, focused))
    assert coverage(patient, build_profile(["chess"])) < 0.5


def test_each_patient_gets_the_helper_sharing_their_interests():
    patients = {"aino": build_profile(["gardening"]), "bob": build_profile(["chess"])}
    helpers = {"mikko": build_profile(["chess"]), "sara": build_profile(["gardening"])}
    assert stable_match(patients, helpers, {}) == {"aino": "sara", "bob": "mikko"}


def test_a_helper_prefers_the_patient_who_has_waited_longer():
    patients = {"aino": build_profile(["gardening"]), "bob": build_profile(["gardening"])}
    helpers = {"mikko": build_profile(["gardening"])}
    assert stable_match(patients, helpers, {"aino": 0.0, "bob": WEEK}) == {"bob": "mikko"}
    assert stable_match(patients, helpers, {"aino": WEEK, "bob": 0.0}) == {"aino": "mikko"}


def test_profiles_from_different_sources_are_compared_offline():
    from_gemini = InterestProfile(("gardening",), ((1.0, 0.0),), "gemini:some-model")
    offline = build_profile(["gardening"])
    assert stable_match({"aino": from_gemini}, {"mikko": offline}, {}) == {"aino": "mikko"}


def test_a_profile_survives_a_round_trip_through_storage():
    profile = build_profile(["gardening"], "I love skiing.")
    assert InterestProfile.from_dict(profile.to_dict()) == profile
