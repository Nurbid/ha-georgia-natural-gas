"""Constants for the Georgia Natural Gas integration."""

from datetime import timedelta

DOMAIN = "georgia_natural_gas"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCOUNT_SELECTION = "account_selection"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_SERVICE_ADDRESS = "service_address"

DEFAULT_SCAN_INTERVAL = timedelta(hours=24)

# Verified GNG export selection index; not the customer-facing account number.
DEFAULT_ACCOUNT_SELECTION = "1"
ACCOUNT_OPTIONS = [
    {"label": "Account 1", "value": DEFAULT_ACCOUNT_SELECTION}
]

STORAGE_VERSION = 1
