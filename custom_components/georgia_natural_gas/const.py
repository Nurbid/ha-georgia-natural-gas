"""Constants for the Georgia Natural Gas integration."""

from datetime import timedelta

DOMAIN = "georgia_natural_gas"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCOUNT_SELECTION = "account_selection"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_SERVICE_ADDRESS = "service_address"
CONF_UPDATE_INTERVAL_DAYS = "update_interval_days"

DEFAULT_UPDATE_INTERVAL_DAYS = 7
MIN_UPDATE_INTERVAL_DAYS = 1
MAX_UPDATE_INTERVAL_DAYS = 30
DEFAULT_SCAN_INTERVAL = timedelta(days=DEFAULT_UPDATE_INTERVAL_DAYS)

# Verified GNG export selection index; not the customer-facing account number.
DEFAULT_ACCOUNT_SELECTION = "1"
ACCOUNT_OPTIONS = [
    {"label": "Account 1", "value": DEFAULT_ACCOUNT_SELECTION}
]

# Detected pricing-plan capability for the selected account.
PLAN_CAPABILITY_BUDGET_BILLING = "budget_billing"
PLAN_CAPABILITY_NONE = "none"
PLAN_CAPABILITY_UNKNOWN = "unknown"

STORAGE_VERSION = 2
