# Georgia Natural Gas (GNG) - Unofficial

A custom [Home Assistant](https://www.home-assistant.io/) integration for customers of **Georgia Natural Gas (GNG)**. It retrieves billing history from the GNG customer portal and exposes usage and cost figures as Home Assistant sensors for the Energy dashboard.

**Requirements:** Home Assistant Core 2026.11.0 or newer.

## Important: unofficial project

This is an **independent, community-maintained** Home Assistant custom integration.

- **Not** an official Georgia Natural Gas / GNG product
- **Not** affiliated with, endorsed by, or supported by Georgia Natural Gas or its parent companies
- Uses the names “GNG” / “Georgia Natural Gas” only to identify the compatible customer portal service
- Subject to GNG’s customer-portal terms; the portal may change or break this integration at any time
- Provided as-is, without warranty

If you need official account support, contact GNG — not the maintainers of this repository.

## Features

- Authenticates with your GNG customer-portal credentials.
- Retrieves detailed billing history from the GNG customer portal.
- Creates sensors for gas usage, billing charges, payments, meter readings, and billing-period details.
- Estimates daily gas consumption from actual billed therm totals and exposes a cumulative therm sensor for Home Assistant Energy.
- Retains previously retrieved billing records locally across Home Assistant restarts.
- Supports manual credential reconfiguration and automatic reauthentication.
- Provides an account-selection setting; the current implementation exposes the verified default account while multi-account portal discovery is still under development.
- Polls the portal every **14 days** by default (configurable, 7–30 days).

## Installation

### HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add this repository URL:

   `https://github.com/Nurbid/ha-georgia-natural-gas`

4. Select **Integration** as the category and add the repository.
5. Find **Georgia Natural Gas (GNG) - Unofficial** in HACS and download it.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Search for **Georgia Natural Gas (GNG) - Unofficial** and enter your GNG portal username and password.

### Manual

1. Copy the `custom_components/gng` directory into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add **Georgia Natural Gas (GNG) - Unofficial** from **Settings → Devices & services**.

## Configuration

- Use the integration entry's **Reconfigure** action to update your GNG username and password. The credentials are validated before the existing entry is updated.
- Use the entry's **Configure** action to choose the GNG account whose billing history should be retrieved.
- Changing the selected account reloads the integration. Billing history is stored separately for each selected account, so switching accounts does not mix their records.
- Automatic reauthentication remains available when GNG rejects previously valid credentials.

The account selector currently contains only the verified default portal selection. Support for discovering and mapping additional GNG accounts is not yet implemented.

## Sensors

The integration creates sensors for the latest available billing record:

| Sensor | Description |
|---|---|
| Gas Consumption | Cumulative therms, with estimated daily allocation for Energy |
| Gas Service Cost | Cumulative actual service cost (USD) for Energy cost tracking |
| Period Service Cost | Latest bill's actual service cost (Gas+Tax+Other+Promo, or Price Plan actual) |
| Actual Bill Charges | Latest Price Plan actual charges (budget billing accounts) |
| Budget Billing Installment | Latest Price Plan installment amount |
| Monthly Budget Variance | Latest Price Plan monthly variance (actual − installment) |
| Accumulated Budget Variance | Running Price Plan budget variance |
| Gas Used | Actual therm consumption for the latest billing period |
| Gas Charges | Gas charges excluding taxes |
| Other Charges | Additional charges |
| Promotional Discounts | Promotional discounts |
| Taxes | Taxes assessed |
| Payments | Sum of payments |
| Balance Forward | Balance carried into the bill |
| Budget Billing Amount | Budget billing amount from Detailed export |
| Guaranteed Billing Amount | Guaranteed billing amount |
| Amount Due | Amount due as reported by GNG |
| Meter Reading | Meter reading reported on the bill |
| Heating Degree Days | Heating degree days for the billing period |
| Average Temperature | Average temperature for the billing period |
| Days of Service | Number of days in the billing period |
| Bill Date | Date of the bill |
| Billing Period Start | Start date of the billing period |
| Billing Period End | End date of the billing period |
| Integration Name | Full integration title (diagnostic; for dashboards) |
| Long Name | Utility long name, e.g. `Georgia Natural Gas` (diagnostic) |
| Short Name | Short label, e.g. `GNG` (diagnostic) |

Default entity ids use the portal account selection slug (not street address), e.g. `sensor.gng_account1_short_name`, `sensor.gng_account1_gas_used`. Dashboard example: `{{ states('sensor.gng_account1_short_name') }}`.

**Important:** GNG provides consumption totals for billing periods, not daily meter readings. The **Gas Consumption** Energy sensor therefore estimates daily usage by distributing each bill's actual therm total evenly across its service days. After the latest bill period, it projects the latest daily average through the previous day. These are estimates, not measured daily readings. When a new bill arrives, the integration replaces the estimate for that billing period with a distribution based on the newly reported total.

Also, **Amount Due** reflects the amount GNG reports as due (which may be a budget-billing amount); it should not be interpreted as the gas-only charge. Use **Period Service Cost** for the latest bill's actual charge total, **Gas Service Cost** for Energy cumulative cost tracking, and **Gas Charges** for commodity charges excluding taxes.

## Home Assistant Energy dashboard

Energy history is published as **external statistics** (`gng:estimated_daily_*`),
not through the `sensor.*` recorder series. That avoids a dual-writer bug where
Home Assistant's recorder resets `sum` on the same statistic ID and creates large
negative Energy spikes.

The **Gas Consumption** / **Gas Service Cost** sensors remain for dashboards and
more-info; they show the current cumulative estimate but are not the Energy
source.

### Gas consumption

1. Open **Settings → Dashboards → Energy**.
2. Under **Gas consumption**, select **Add gas source**.
3. Choose **statistic** / browse statistics and select
   **GNG • Estimated daily consumption • …** (`gng:estimated_daily_consumption_…`).

### Gas cost

1. In the same gas source, set the cost to the statistic
   **GNG • Estimated daily service cost • …**
   (`gng:estimated_daily_service_cost_…`).
2. Do **not** point Energy at the **Gas Service Cost** sensor entity.

Cost values come from GNG Price Plan **Actual Bill Charges** when available.
If Price Plan history is missing (non-budget accounts), the integration falls
back to `Gas Charges + Taxes + Other Charges + Promotional Discounts` from
the Detailed billing export. Budget installments and payment history are
never used as Energy costs.

Because GNG only supplies billing-period totals, the integration distributes
each bill's actual therms and actual service cost evenly across the days in
that billing period. It then projects the latest daily average through
yesterday until a newer bill arrives. The current day is not counted as a
complete day. These are estimates, not measured daily meter or rate data.

Daily estimates are republished after each portal poll and again at local
**00:05** without contacting GNG, so Energy keeps advancing between weekly
polls. Re-publishes upsert by timestamp, so a new bill can replace earlier
estimates for that period without duplicating rows.

Separate external statistics are also published for billed therm usage, gas
charges excluding taxes, meter CCF, and reconciled actual service cost. They
are intended for Statistics Graph cards.

If you previously selected the **Gas Consumption** / **Gas Service Cost**
sensors as Energy sources, remove them and add the `gng:estimated_daily_*`
statistics above. Old sensor statistics may show a one-time negative spike from
the recorder `sum` reset; the new external series are the supported path.

## Data and polling

- The integration requests Detailed billing data and Price Plan
  (`/EppHistorySpreadsheet`) history from the GNG customer portal.
- The first update downloads up to ~24 months of Detailed history.
- Later updates request the current bill only (merged into local history) plus
  the full Price Plan spreadsheet (no date-range filter on that export).
- The default update interval is **7 days** and is configurable in the
  integration options (1–30 days).
- Retrieved billing history is stored locally by Home Assistant and merged with subsequent downloads.
- Historical records are kept separately for each configured portal account selection.
- Multi-account portal discovery is not implemented yet; selection remains `"1"`.
- Data availability depends on GNG's portal and its underlying API. Changes to that service may interrupt the integration.

## Troubleshooting

- If authentication fails after changing your GNG password, use the **Reconfigure** action on the integration and enter your current username and password.
- If the integration detects an authentication failure, Home Assistant will prompt you to reauthenticate.
- Check **Settings → System → Logs** for integration errors.
- If GNG changes its customer portal or API, data retrieval may stop working. Please open an issue with relevant logs, but remove usernames, account numbers, addresses, tokens, and other personal information first.

## Privacy and security

Your GNG credentials are provided through Home Assistant's config flow and stored with the config entry. Billing information is retrieved from GNG and stored locally by Home Assistant. The integration does not intentionally publish your account information.

Do not post credentials, session tokens, account numbers, addresses, or unredacted billing exports in GitHub issues.

## Disclaimer / trademarks

This project is provided as-is, without warranty. Georgia Natural Gas may change or restrict its customer portal at any time. Use of this integration is subject to the terms and availability of the GNG customer portal.

“Georgia Natural Gas,” “GNG,” and related marks are the property of their respective owners. This project is not affiliated with those owners. Mentions of those names are for identification of the third-party service this integration works with.
