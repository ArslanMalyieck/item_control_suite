# item_control_suite

Purchase Invoice **Amount-based pricing** + **Sales / Buying / Asset Items** views + **strict server-side Item visibility** for ERPNext v16.

## Installation

```bash
cd ~/frappe-bench
bench get-app item_control_suite https://github.com/your-org/item_control_suite.git
bench --site YOURSITE install-app item_control_suite
bench --site YOURSITE migrate
bench build
bench restart
```

## Purchase Invoice - Amount input

On `Purchase Invoice > Items` a custom field is added automatically:

| Field | Label | Type |
|---|---|---|
| `custom_input_amount` | Amount | Currency |

Workflow: select item → enter **Qty** → enter **Amount** → the standard **Rate** is derived (`rate = amount / qty`) and ERPNext's own calculation produces `amount = qty * rate` (== the entered amount).

- Verified examples: Qty 10 + Amount 1000 → Rate 100 → Amount 1000; Qty 5 + Amount 1250 → Rate 250 → Amount 1250.
- Qty = 0 → no derivation (no division by zero).
- Amount empty/0 → standard rate/amount flow untouched (no stale values).
- Multiple rows are independent; stock and non-stock items both work.
- Rounding uses rate precision 6 (server, `flt`) and ERPNext's currency precision for the final amount.
- No ERPNext core files are modified; the hook runs on `before_validate`.

## Workspace views

The standard Item links in Selling / Buying / Assets are replaced by dedicated list pages:

| Workspace | Link | Filter (server enforced) |
|---|---|---|
| Selling | Sales Items | `is_sales_item = 1` |
| Buying | Buying Items | `is_purchase_item = 1` |
| Assets | Asset Items | `is_fixed_asset = 1` |

The Item DocType itself is untouched (no duplicate masters). Filters are **invisible in the UI** (injected per request, not added as removable chips).

## Security model (server side)

Roles:

- **Item Manager** (standard ERPNext role) - may create/edit Items.
- **Item Master Allow** - created by this app; full Item visibility.

Enforcement (all at the SQL / permission layer - no client-side security):

1. `permission_query_conditions` on Item - Frappe appends it to every native query (lists, reports, `frappe.get_list`, link search `frappe.desk.search.search_link` / `search_widget`):
   - Admin / System Manager / **Item Master Allow** → no restriction.
   - Everyone else → the workspace context carried in the request narrows the query (`is_sales_item = 1` / `is_purchase_item = 1` / `is_fixed_asset = 1`); without a workspace context only operational items are visible: `is_fixed_asset = 0 AND (is_sales_item = 1 OR is_purchase_item = 1)`. Hidden items (no flags) are never retrievable.
2. `has_permission` on Item - guards direct document access (`/app/item/ITEM-X`, `frappe.get_doc`): non-privileged users may only open operational items; fixed-asset / hidden items are denied with `PermissionError`.
3. Creation guard (`before_validate` on Item): create/edit requires **Item Manager** (or Admin / System Manager).

`Item Master Allow` is created idempotently on install and is never auto-assigned.

## Test data

Idempotent seed via `bench --site SITE execute item_control_suite.install.seed_test_items`:

- `TEST-SALES-001` (sales only), `TEST-BUY-001` (purchase only), `TEST-ASSET-001` (fixed asset), `TEST-BOTH-001` (sales + purchase), `TEST-HIDDEN-001` (no flags).

## Tests

```bash
bench --site SITE run-tests --app item_control_suite
```

## Uninstall / migration notes

`bench --site SITE uninstall-app item_control_suite` removes the custom field and pages; roles and workspace links are left for the administrator to clean up (removing them is safe). Migrations are idempotent (no duplicate fields / roles).
