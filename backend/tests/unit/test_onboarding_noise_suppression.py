import os

os.environ.setdefault("APP_ENV", "test")

from app.services import onboarding


def test_noise_suppression_allows_meal_confirmation_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_meal_details",
        "y",
        {"meal_confirm_pending": True},
    ) is False


def test_noise_suppression_allows_preventive_confirmation_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_preventive",
        "yes",
        {"preventive_confirm_pending": True},
    ) is False


def test_noise_suppression_still_blocks_ack_without_confirmation() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_meal_details",
        "y",
        {"meal_confirm_pending": False},
    ) is True


def test_noise_suppression_allows_future_confirmation_flags() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_custom_step",
        "yes",
        {"custom_confirm_pending": True},
    ) is False


def test_noise_suppression_ignores_non_pending_confirmation_flags() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_custom_step",
        "yes",
        {"custom_confirm_pending": False},
    ) is True


def test_binary_confirmation_parser_accepts_yes_variants() -> None:
    assert onboarding._resolve_binary_confirmation_reply("y") == "yes"
    assert onboarding._resolve_binary_confirmation_reply("YES") == "yes"
    assert onboarding._resolve_binary_confirmation_reply("yes!") == "yes"


def test_binary_confirmation_parser_accepts_no_variants() -> None:
    assert onboarding._resolve_binary_confirmation_reply("n") == "no"
    assert onboarding._resolve_binary_confirmation_reply("No") == "no"
    assert onboarding._resolve_binary_confirmation_reply("no.") == "no"


def test_binary_confirmation_parser_returns_none_for_non_binary_reply() -> None:
    assert onboarding._resolve_binary_confirmation_reply("yes but no egg") is None
