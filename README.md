# Georgia Natural Gas

A custom [Home Assistant](https://www.home-assistant.io/) integration for **Georgia Natural Gas (GNG)**. It retrieves billing history from the GNG customer portal and exposes the latest billing and natural-gas usage figures as Home Assistant sensors.

This is an unofficial, community-maintained integration. It is not affiliated with or endorsed by Georgia Natural Gas.

## Features

- Authenticates with your Georgia Natural Gas customer-portal credentials.
- Retrieves detailed billing history from the GNG customer portal.
- Creates sensors for gas usage, billing charges, payments, meter readings, and billing-period details.
- Retains previously retrieved billing records locally across Home Assistant restarts.
- Supports reauthentication when your GNG password changes.
- Polls the portal every 24 hours by default.

## Installation

### HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add this repository URL:

   `https://github.com/Nurbid/ha-georgia-natural-gas`

4. Select **Integration** as the category and add the repository.
5. Find **Georgia Natural Gas** in HACS and download it.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Search for **Georgia Natural Gas** and enter your GNG portal username and password.

### Manual

1. Copy the `custom_components/georgia_natural_gas` directory into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add **Georgia Natural Gas** from **Settings → Devices & services**.

## Sensors

The integration creates sensors for the latest available billing record:

| Sensor | Description |
|---|---|
| Gas Used | Natural gas consumption in therms |
| Gas Charges | Gas charges excluding taxes |
| Other Charges | Additional charges |
| Promotional Discounts | Promotional discounts |
| Taxes | Taxes assessed |
| Payments | Sum of payments |
| Balance Forward | Balance carried into the bill |
| Budget Billing Amount | Budget billing amount |
| Guaranteed Billing Amount | Guaranteed billing amount |
| Amount Due | Amount due as reported by GNG |
| Meter Reading | Meter reading reported on the bill |
| Heating Degree Days | Heating degree days for the billing period |
| Average Temperature | Average temperature for the billing period |
| Days of Service | Number of days in the billing period |
| Bill Date | Date of the bill |
| Billing Period Start | Start date of the billing period |
| Billing Period End | End date of the billing period |

**Important:** GNG provides consumption totals for billing periods, not daily meter readings. This integration does not estimate or distribute billing-period consumption into daily usage.

Also, **Amount Due** reflects the amount GNG reports as due (which may be a budget-billing amount); it should not be interpreted as the gas-only charge. Use **Gas Charges** for gas charges excluding taxes.

## Data and polling

- The integration requests detailed billing data from the GNG customer portal.
- Updates are scheduled every 24 hours.
- Retrieved billing history is stored locally by Home Assistant and merged with subsequent downloads.
- The initial download is limited to the available rolling history requested from the portal.
- Data availability depends on GNG's portal and its underlying API. Changes to that service may interrupt the integration.

## Troubleshooting

- If authentication fails after changing your GNG password, use the **Reconfigure** action on the integration and enter the updated password.
- Check **Settings → System → Logs** for integration errors.
- If GNG changes its customer portal or API, data retrieval may stop working. Please open an issue with relevant logs, but remove usernames, account numbers, addresses, tokens, and other personal information first.

## Privacy and security

Your GNG credentials are provided through Home Assistant's config flow and stored with the config entry. Billing information is retrieved from GNG and stored locally by Home Assistant. The integration does not intentionally publish your account information.

Do not post credentials, session tokens, account numbers, addresses, or unredacted billing exports in GitHub issues.

## Disclaimer

This project is provided as-is, without warranty. Georgia Natural Gas may change or restrict its customer portal at any time. Use of this integration is subject to the terms and availability of the GNG customer portal.
