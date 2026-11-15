# Energy cost + multi-source implementation plan

> Implement on `feat/energy-cost-multisource` with one commit per task below.

**Goal:** Energy-ready cumulative USD cost entity + Price Plan fetch + weekly configurable poll + incremental Detailed downloads.

**Architecture:** Separate `PricePlanPeriod` model; reconcile Actual Bill Charges onto billing periods; mirror daily therm allocation for cost; keep unused sources stubbed.

**Stack:** Home Assistant custom component (Python), existing aiohttp client, recorder statistics APIs.

## Global constraints

- Do not fetch Usage/Bill/Payment/Summary in this branch.
- Default update interval: 7 days; option range 1–30.
- Multi-account remains selection `"1"`.
- No secrets in logs or docs.

---

### Task 1: Docs

**Files:** `_docs/2026-11-15-energy-cost-multisource-design.md`, this plan.

- [x] Write design + plan
- [ ] Commit: `docs: energy cost multisource design`

### Task 2: API — EppHistory + incremental Detailed

**Files:** `custom_components/georgia_natural_gas/api.py`, `const.py`

- Add `download_authlink_file(path, *, referer)`
- Add `download_price_plan_history()` → `/EppHistorySpreadsheet`
- Extend `download_billing_data(..., is_current_bill_selected=False)`
- Add `CONF_UPDATE_INTERVAL_DAYS`, `DEFAULT_UPDATE_INTERVAL_DAYS=7`, bump `STORAGE_VERSION=2`

- [ ] Commit: `feat(api): add EppHistory and current-bill download`

### Task 3: Models — PricePlan + cost resolve

**Files:** `custom_components/georgia_natural_gas/models.py` (or `price_plan.py` + `reconcile.py`)

- `PricePlanPeriod` + CSV parse/serialize/merge
- `resolve_actual_service_cost(billing, price_plan|None) -> (Decimal, source)`
- `PLAN_CAPABILITY_*` constants

- [ ] Commit: `feat(models): parse Price Plan and resolve actual cost`

### Task 4: Statistics — daily cost series

**Files:** `custom_components/georgia_natural_gas/statistics.py`, `tests/test_statistics.py`

- Generalize daily allocator; `build_daily_cost_statistics(records, cost_by_bill_date, ...)`
- External series for actual service cost (optional alongside excl-tax charges)

- [ ] Commit: `feat(stats): add estimated daily gas service cost`

### Task 5: Sensors + coordinator + options

**Files:** `sensor.py`, `coordinator.py`, `config_flow.py`, `translations/en.json`, `README.md`

- Sensors: `gas_service_cost` (Energy total cost), latest actual charges, installment, monthly/accumulated variance
- Coordinator: full vs current Detailed; always EppHistory; store v2; import cost stats; configurable interval
- Options: update interval days
- README Energy cost steps

- [ ] Commit: `feat: wire Energy total-cost sensor and weekly poll`

### Task 6: Tests + verify

- Unit tests for price-plan parse, cost resolve, daily cost totals
- Run: `python -m pytest tests/ -v`

- [ ] Commit: `test: cover Price Plan cost path`
