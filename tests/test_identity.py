"""Tests for GNG account identity presentation."""

from custom_components.gng.identity import (
    account_device_identifier,
    account_device_name,
    account_display_name,
    account_entity_object_id,
    account_entity_unique_id,
    account_selection_slug,
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
        == "GNG • 555002240-2024212 • 123 Some Street"
    )


def test_builds_account_label_without_address() -> None:
    """Missing address still keeps the GNG short-name prefix."""
    assert (
        account_display_name("5550022402024212", "")
        == "GNG • 555002240-2024212"
    )


def test_account_selection_slug_and_device_name() -> None:
    """Selection index drives object_id; address drives friendly device name."""
    assert account_selection_slug("1") == "account1"
    assert account_device_name("1", "123 Some Street") == "GNG • 123 Some Street"
    assert account_device_name("1") == "GNG account1"
    assert account_entity_object_id("1", "gas_used") == "gng_account1_gas_used"
    assert account_device_identifier("entry-id", "1") == "entry-id_account1"
    assert (
        account_entity_unique_id("entry-id", "1", "gas_used")
        == "entry-id_account1_gas_used"
    )
