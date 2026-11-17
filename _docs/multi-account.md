# Multi-account model (prep)

## Target shape

One GNG **login** (config entry) may later expose multiple **service accounts**.

```
Config entry (portal username)
  ├─ Device: GNG • 123 Some St  → sensors sensor.gng_account1_*
  └─ Device: GNG • 456 Other St → sensors sensor.gng_account2_*
```

- Each service account = its own Home Assistant **device** and sensor set.
- Energy dashboard: user adds each account’s Gas Consumption / cost entities as separate gas sources.
- Storage remains namespaced by portal `account_selection`.

## Identity rules (implemented now)

| Layer | Format | Example |
| --- | --- | --- |
| Portal selection | `"1"`, `"2"`, … | `"1"` |
| Slug | `account{selection}` | `account1` |
| Device name (friendly) | `GNG • {address}` (fallback `GNG account{selection}`) | `GNG • 123 Some Street` |
| Device identifier | `{entry_id}_account{selection}` | `…_account1` |
| Entity unique_id | `{entry_id}_account{selection}_{key}` | `…_account1_gas_used` |
| Suggested object_id | `gng_account{selection}_{key}` | `gng_account1_gas_used` |
| Default entity_id | `sensor.gng_account{selection}_{key}` | `sensor.gng_account1_gas_used` |

Entity ids come from `suggested_object_id`, not from the friendly device name. Account number stays on device **serial_number** (and config entry title).

## Not implemented yet

- Discovering portal accounts beyond selection `"1"`
- Creating multiple devices from one login in one setup
- Parallel polling of multiple accounts

When a second real portal account is available, extend options/discovery and spawn one device per enabled selection using the identity helpers above.
