# Naming conventions

| Layer | Value |
| --- | --- |
| Integration title (HACS / Add Integration / `manifest.name`) | `Georgia Natural Gas (GNG) - Unofficial` |
| Domain / package / entity prefix | `gng` (`custom_components/gng/`, `sensor.gng_*`) |
| Device / short display / stats prefix | `GNG` (`SHORT_NAME`) |
| Full utility name (docs / consts) | `Georgia Natural Gas` (`LONG_NAME`) |
| Device manufacturer | `Community` (not the utility’s legal name) |

Names identify the compatible customer portal. This project is unofficial and unaffiliated.

## Price Plan sensors and “Unavailable”

These entities require a successful Price Plan (`/EppHistorySpreadsheet`) history:

- Actual Bill Charges
- Budget Billing Installment
- Monthly Budget Variance
- Accumulated Budget Variance

They stay **Unavailable** when `plan_capability` is not `budget_billing` or Price Plan rows are empty (fetch failed, non-budget account, or not yet refreshed). They are not legacy leftovers.
