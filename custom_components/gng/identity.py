"""Helpers for presenting GNG account identity in Home Assistant."""

import re

from .const import SHORT_NAME


def format_account_number(account_number: str) -> str:
    """Format a 16-digit GNG account number as 9-7 digits."""
    value = account_number.strip()
    digits = re.sub(r"\D", "", value)

    if len(digits) == 16:
        return f"{digits[:9]}-{digits[9:]}"

    return value


def account_selection_slug(account_selection: str) -> str:
    """Stable slug for portal account selection (e.g. '1' → 'account1')."""

    selection = str(account_selection).strip() or "1"
    return f"account{selection}"


def account_device_name(account_selection: str) -> str:
    """Device name that slugs to sensor.gng_accountN_* entity ids."""

    return f"{SHORT_NAME} {account_selection_slug(account_selection)}"


def account_device_identifier(entry_id: str, account_selection: str) -> str:
    """Stable device registry id segment for one service account."""

    return f"{entry_id}_{account_selection_slug(account_selection)}"


def account_entity_unique_id(
    entry_id: str,
    account_selection: str,
    key: str,
) -> str:
    """Stable entity unique_id including account selection."""

    return f"{entry_id}_{account_selection_slug(account_selection)}_{key}"


def account_display_name(account_number: str, address: str) -> str:
    """Return the customer-facing account and service-address label."""
    number = format_account_number(account_number)
    if address:
        return f"{SHORT_NAME} • {number} • {address}"
    return f"{SHORT_NAME} • {number}"
