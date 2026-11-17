# Multi-account model (prep)

## Target shape

One GNG **login** (config entry) may later expose multiple **service accounts**.

```
Config entry (portal username)
  ├─ Device: GNG account1  → sensors sensor.gng_account1_*
  └─ Device: GNG account2  → sensors sensor.gng_account2_*
```

- Each service account = its own Home Assistant **device** and sensor set.
- Energy dashboard: user adds each account’s Gas Consumption / cost entities as separate gas sources.
- Storage remains namespaced by portal `account_selection`.

## Identity rules (implemented now)

| Layer | Format | Example |
| --- | --- | --- |
| Portal selection | `"1"`, `"2"`, … | `"1"` |
| Slug | `account{selection}` | `account1` |
| Device name | `GNG account{selection}` | `GNG account1` |
| Device identifier | `{entry_id}_account{selection}` | `…_account1` |
| Entity unique_id | `{entry_id}_account{selection}_{key}` | `…_account1_gas_used` |
| Default entity_id | `sensor.gng_account{selection}_{key}` | `sensor.gng_account1_gas_used` |

Friendly address / account number go on the device **model** / **serial_number** (and config entry title), not in the entity_id slug.

## Not implemented yet

- Discovering portal accounts beyond selection `"1"`
- Creating multiple devices from one login in one setup
- Parallel polling of multiple accounts

When a second real portal account is available, extend options/discovery and spawn one device per enabled selection using the identity helpers above.
