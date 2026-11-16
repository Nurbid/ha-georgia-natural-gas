# Naming conventions

| Layer | Value |
| --- | --- |
| Integration title (HACS / Add Integration / `manifest.name`) | `GNG (unofficial)` |
| Domain / package / entity prefix | `gng` (`custom_components/gng/`, `sensor.gng_*`) |
| Device / short display / stats prefix | `GNG` |
| Device manufacturer | `Community` |
| README identification of the utility | “Georgia Natural Gas (GNG)” only as the compatible service |

Names identify the compatible customer portal. This project is unofficial and unaffiliated.

## Price Plan sensors and “Unavailable”

These entities require a successful Price Plan (`/EppHistorySpreadsheet`) history:

- Actual Bill Charges
- Budget Billing Installment
- Monthly Budget Variance
- Accumulated Budget Variance

They stay **Unavailable** when `plan_capability` is not `budget_billing` or Price Plan rows are empty (fetch failed, non-budget account, or not yet refreshed). They are not legacy leftovers.
