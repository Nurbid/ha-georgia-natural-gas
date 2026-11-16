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


def account_display_name(account_number: str, address: str) -> str:
    """Return the customer-facing account and service-address label."""
    number = format_account_number(account_number)
    if address:
        return f"{SHORT_NAME} • {number} • {address}"
    return f"{SHORT_NAME} • {number}"
