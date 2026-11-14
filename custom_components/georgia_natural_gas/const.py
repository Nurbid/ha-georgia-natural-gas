"""Constants for the Georgia Natural Gas integration."""

from datetime import timedelta

DOMAIN = "georgia_natural_gas"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = timedelta(hours=24)

# Verified against the GNG Detailed Billing Data export.
DEFAULT_ACCOUNT_NUMBERS = ("1",)

STORAGE_VERSION = 1