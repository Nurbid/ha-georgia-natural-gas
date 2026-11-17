# Future GNG data sources (stubs)

Verified export endpoints exist (see `gng-client` discovery) but are **not** polled by this integration yet. They are reserved for later phases once Energy consumption + total cost are stable.

| Source | Export | Intended use | Why deferred |
| --- | --- | --- | --- |
| Usage History | `/UsageHistorySpreadsheet` | Therms / HDD / temp cross-check | Overlaps Detailed |
| Bill History | `/BillingHistorySpreadsheet` | Installment / total validation | Overlaps Detailed + Price Plan |
| Payment History | `/PaymentHistorySpreadsheet` | Cash-flow sensors | Not Energy cost |
| DownloadData Summary | Summary CSV | Reconciliation totals | Derivable from Detailed |
| Other price plans | Unknown URLs | Non-budget plan types | Need live account samples |

## Plan-capability stub

`plan_capability` on the coordinator:

- `budget_billing` — EppHistory rows present
- `none` — fetch succeeded, empty history
- `unknown` — fetch failed / unparsed

Future plan types should plug into the same capability + cost-resolver interface without assuming `/BudgetBillingPlan` is universal.

## Multi-account stub

Portal `AccountNumbers` selection remains `"1"`. Coordinator storage keys already namespace by selection for a future discovery UI. Device / entity identity already includes `account{N}` — see [multi-account.md](multi-account.md).
