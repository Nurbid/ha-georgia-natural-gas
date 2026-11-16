# Energy cost + multi-source design

**Date:** 2026-11-15  
**Branch:** `feat/energy-cost-multisource`  
**Status:** Approved for implementation

## Goal

Add Home Assistant Energy Dashboard **total cost** support using GNG **Actual Bill Charges**, without conflating budget-billing installments or payments. Fetch only sources required for gas consumption + total cost. Keep portal load low after the initial history seed.

## Decisions

| Topic | Choice |
| --- | --- |
| Energy total cost | Cumulative **Actual Bill Charges** (USD, `total_increasing`) |
| Cost authority | Price Plan / EppHistory when present |
| Cost fallback | `Gas Charges + Taxes + Other Charges (+ Promo as exported)` from DownloadData Detailed |
| Sources polled | Detailed + EppHistory only (Usage / Bill / Payment / Summary deferred) |
| Multi-account | Stub selection `"1"`; coordinator shaped per-account for later |
| Non-budget accounts | Fail soft: no EppHistory → Detailed-component cost; variance sensors unavailable |
| Other plan types | Capability enum + stubs (`budget_billing` \| `none` \| `unknown`) |
| Poll interval | Configurable days; **default 7** |
| First poll | Full ~24-month Detailed download |
| Later polls | Detailed `IsCurrentBillSelected=True` (merge/upsert); EppHistory always full CSV |
| Daily cost shape | Even split across service days (same pattern as therms); estimates |

## Architecture

```
Login
  ├─ DownloadData Detailed (full | current)
  └─ GET /EppHistorySpreadsheet?Token=&nr=1
       ↓
BillingRecord store  +  PricePlanPeriod store
       ↓
Reconcile by Bill Date → actual_service_cost per period
       ↓
Sensors: gas_consumption (thm) + gas_service_cost (USD) — display only
       ↓
async_add_external_statistics (gng:estimated_daily_* ; no recorder dual-write)
```

## Authoritative fields

| Field | Source |
| --- | --- |
| Therms, period bounds, meter, HDD, temp | DownloadData Detailed |
| Actual service cost | EppHistory `Actual Bill Charges` else Detailed components |
| Installment / variance | EppHistory only |
| Payments | Not used for Energy cost (future) |

## Discrepancy handling

- Prefer Price Plan actual totals when present; do not silently rewrite Detailed component fields.
- Log mismatches (no account PII) when `Gas+Tax+Other` ≠ Price Plan actual.
- Prefer Price Plan / Bill History for installment when they disagree with Detailed (Bill History not fetched this phase; Price Plan wins for installment sensors).

## Out of scope (this branch)

- Usage / Bill / Payment / Summary live fetches
- Multi-account portal discovery
- Non-budget plan spreadsheet URLs (stubbed)
- Weather-normalized / baseline analytics
