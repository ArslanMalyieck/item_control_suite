import frappe
from frappe import _
from frappe.utils import flt

# ============================================================
# ITEM CREATION RESTRICTION
# ============================================================
# Only users with the standard ERPNext "Item Manager" role (or
# Administrator / System Manager) may create or edit Items.
# Workspace views (Sales Items etc.) never grant write access.
# ============================================================

ITEM_MANAGER_ROLE = "Item Manager"


def check_item_create_permission(doc, method=None):
	if frappe.session.user == "Administrator":
		return

	roles = frappe.get_roles()

	if "System Manager" in roles or ITEM_MANAGER_ROLE in roles:
		return

	frappe.throw(
		_("Only users with the {0} role can create or edit Items.").format(ITEM_MANAGER_ROLE),
		frappe.PermissionError,
	)
