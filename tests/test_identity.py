"""Tests for GNG account identity presentation."""

from custom_components.georgia_natural_gas.identity import (
    account_display_name,
    format_account_number,
)


def test_formats_sixteen_digit_account_number() -> None:
    """A 16-digit GNG account number is formatted in 9-7 groups."""
    assert format_account_number("5550022402024212") == "555002240-2024212"


def test_preserves_already_formatted_account_number() -> None:
    """An account number already formatted by GNG is unchanged."""
    assert format_account_number("555002240-2024212") == "555002240-2024212"


def test_preserves_unrecognized_account_number_format() -> None:
    """Unknown account-number formats are not guessed or rewritten."""
    assert format_account_number("1310757040") == "1310757040"


def test_builds_account_and_service_address_label() -> None:
    """The account selector and config entry use both identity fields."""
    assert (
        account_display_name("5550022402024212", "123 Some Street")
        == "555002240-2024212 • 123 Some Street"
    )
