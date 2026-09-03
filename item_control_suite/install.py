import frappe

# ============================================================
# INSTALLATION / MIGRATION HOOKS
# ============================================================

FULL_VISIBILITY_ROLE = "Item Master Allow"


def after_install():
	_create_full_visibility_role()
	_set_pi_field_property_setters()
	_update_workspace_links()
	frappe.clear_cache()


# ============================================================
# PURCHASE INVOICE ITEM - read-only rate + amount
# ============================================================
# The user only enters Qty and the custom Amount
# (custom_input_amount). The standard "rate" and "amount" columns are
# read-only; rate is derived as custom_input_amount / qty in
# before_validate (and live in the UI) and ERPNext's own calculation
# keeps amount = qty * rate == custom_input_amount.
# ============================================================

def _set_pi_field_property_setters():
	settings = [
		("Purchase Invoice Item", "rate", "read_only", 1),
		("Purchase Invoice Item", "amount", "read_only", 1),
	]

	for dt, fieldname, prop, value in settings:
		name = f"{dt}-{fieldname}-{prop}"

		if frappe.db.exists("Property Setter", name):
			continue

		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": dt,
				"field_name": fieldname,
				"property": prop,
				"property_type": "Check",
				"value": value,
			}
		).insert(ignore_permissions=True)
		print(f"Property Setter: {dt}.{fieldname} -> {prop} = {value}")


def _create_full_visibility_role():
	"""Create the 'Item Master Allow' role if it does not exist yet."""
	if frappe.db.exists("Role", FULL_VISIBILITY_ROLE):
		return

	frappe.get_doc(
		{"doctype": "Role", "role_name": FULL_VISIBILITY_ROLE, "desk_access": 1}
	).insert(ignore_permissions=True)
	print(f"Role created: {FULL_VISIBILITY_ROLE}")


# ============================================================
# WORKSPACE CONFIGURATION
# ============================================================
# The standard ERPNext Item links inside Selling / Buying / Assets
# point to the specialised list pages instead:
#   Selling -> "Sales Items"  (is_sales_item = 1)
#   Buying  -> "Buying Items" (is_purchase_item = 1)
#   Assets  -> "Asset Items"  (is_fixed_asset = 1)
# This is repeatable - running it again only updates existing links.
# ============================================================

def _update_workspace_links():
	_replace_item_link("Selling", "Sales Items", "item-sales")
	_replace_item_link("Buying", "Buying Items", "item-buying")
	_add_page_link("Assets", "Asset Items", "item-asset")


def _replace_item_link(workspace_name, label, page_name):
	ws = frappe.get_doc("Workspace", workspace_name)
	changed = False

	for link in ws.links:
		if link.link_type == "DocType" and link.link_to == "Item":
			link.label = label
			link.link_type = "Page"
			link.link_to = page_name
			changed = True

	if changed:
		ws.save(ignore_permissions=True)
		print(f"Workspace '{workspace_name}': Item link -> {label}")


def _add_page_link(workspace_name, label, page_name):
	ws = frappe.get_doc("Workspace", workspace_name)

	for link in ws.links:
		if link.link_to == page_name:
			return

	ws.append("links", {"label": label, "link_type": "Page", "link_to": page_name})
	ws.save(ignore_permissions=True)
	print(f"Workspace '{workspace_name}': added {label}")


# ============================================================
# TEST DATA SEED (idempotent - safe to run repeatedly)
# ============================================================

TEST_ITEMS = (
	{
		"item_code": "TEST-SALES-001",
		"item_name": "Test Sales Item",
		"is_sales_item": 1,
		"is_purchase_item": 0,
		"is_fixed_asset": 0,
	},
	{
		"item_code": "TEST-BUY-001",
		"item_name": "Test Buying Item",
		"is_sales_item": 0,
		"is_purchase_item": 1,
		"is_fixed_asset": 0,
	},
	{
		"item_code": "TEST-ASSET-001",
		"item_name": "Test Asset Item",
		"is_sales_item": 0,
		"is_purchase_item": 0,
		"is_fixed_asset": 1,
	},
	{
		"item_code": "TEST-BOTH-001",
		"item_name": "Test Both Item",
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"is_fixed_asset": 0,
	},
	{
		"item_code": "TEST-HIDDEN-001",
		"item_name": "Test Hidden Item",
		"is_sales_item": 0,
		"is_purchase_item": 0,
		"is_fixed_asset": 0,
	},
)


def seed_test_items():
	"""Create the documented test Items if they do not exist."""
	asset_category = frappe.db.get_value("Asset Category", {}, "name") or None

	# a supplier for Purchase Invoice tests
	if not frappe.db.exists("Supplier", "Test Supplier"):
		supplier = frappe.new_doc("Supplier")
		supplier.supplier_name = "Test Supplier"
		supplier.supplier_group = "All Supplier Groups"
		supplier.flags.ignore_permissions = True
		supplier.insert(ignore_permissions=True)
		print("Test supplier created: Test Supplier")

	for spec in TEST_ITEMS:
		if frappe.db.exists("Item", spec["item_code"]):
			continue

		doc = frappe.new_doc("Item")
		doc.update(
			{
				"item_code": spec["item_code"],
				"item_name": spec["item_name"],
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_sales_item": spec["is_sales_item"],
				"is_purchase_item": spec["is_purchase_item"],
				"is_fixed_asset": spec["is_fixed_asset"],
				"asset_category": asset_category if spec["is_fixed_asset"] else None,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		print(f"Test item created: {spec['item_code']}")
