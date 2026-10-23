"""The gates a future upstream release has to pass before this edition publishes."""

from scripts.upstream_sync import already_synced, decide, stable_release


def test_a_stable_release_is_discovered_and_a_draft_is_not():
    assert stable_release("v1.0.5")
    assert not stable_release("v1.0.5", draft=True)
    assert not stable_release("v1.0.5", prerelease=True)
    assert not stable_release("desktop-v0.1.23")


def test_the_same_release_is_not_prepared_twice():
    assert already_synced("v1.0.5", {"v1.0.5"}, set())
    assert already_synced("v1.0.6", set(), {"upstream/v1.0.6"})
    assert not already_synced("v1.0.6", {"v1.0.5"}, set())


def test_a_new_clean_tested_release_may_publish():
    decision = decide("v1.0.6", checks_passed=True)
    assert decision.action == "publish"


def test_a_conflict_asks_for_a_person_and_does_not_publish():
    decision = decide("v1.0.6", conflicts=["scripts/rebrand.py"], checks_passed=True)
    assert decision.action == "review"


def test_a_failed_build_never_publishes():
    decision = decide("v1.0.6", checks_passed=False)
    assert decision.action == "stop"


def test_a_repeated_release_is_skipped_even_when_its_checks_would_pass():
    decision = decide("v1.0.5", merged_tags={"v1.0.5"}, checks_passed=True)
    assert decision.action == "skip"
