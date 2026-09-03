import json

import frappe

# ============================================================
# SERVER-SIDE ITEM VISIBILITY - permission level
# ============================================================
# Two hooks cover every native Item reader (list views, reports,
# frappe.get_list/get_all, link-field search via frappe.desk.search,
# standard search APIs) because Frappe appends these conditions at
# the SQL layer - they cannot be bypassed with client filters,
# URL parameters or or_filters tricks.
#
#  - "Item Master Allow", Administrator, System Manager:
#        complete visibility (no condition)
#  - everyone else:
#        visibility depends on the REQUEST context. The specialized
#        workspace pages send one of the protected flag filters in
#        the request, which maps to the matching workspace rule:
#           Sales Items  -> is_sales_item   = 1
#           Buying Items -> is_purchase_item = 1
#           Asset Items  -> is_fixed_asset  = 1
#        Without a workspace context (plain Item list, link fields,
#        search, APIs) only "operational" items are visible:
#           is_fixed_asset = 0 AND (is_sales_item = 1 OR is_purchase_item = 1)
#        Hidden items (all flags off) and fixed-asset items are never
#        retrievable outside their dedicated workspace context.
# ============================================================

FULL_VISIBILITY_ROLE = "Item Master Allow"
WORKSPACE_FIELDS = ("is_sales_item", "is_purchase_item", "is_fixed_asset")


def _user_has_full_visibility(user=None):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return "System Manager" in roles or FULL_VISIBILITY_ROLE in roles


def _request_workspace_field():
	"""Return the workspace flag carried by the current request, if any."""
	form_dict = getattr(frappe.local, "form_dict", None)
	if form_dict is None:
		return None

	filters = form_dict.get("filters")
	if not filters:
		return None

	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			return None

	if isinstance(filters, dict):
		for f in WORKSPACE_FIELDS:
			if filters.get(f) == 1:
				return f
		return None

	if isinstance(filters, list):
		workspace = None
		for f in filters:
			if isinstance(f, (list, tuple)) and len(f) > 1 and f[1] in WORKSPACE_FIELDS:
				# first protected flag seen defines the workspace context
				if workspace is None:
					workspace = f[1]
		return workspace

	return None


def get_item_permission_query_conditions(user=None):
	if _user_has_full_visibility(user):
		return ""

	workspace_field = _request_workspace_field()

	if workspace_field:
		return f"({workspace_field} = 1)"

	return "(is_fixed_asset = 0 and (is_sales_item = 1 or is_purchase_item = 1))"


def has_permission(doc, ptype, user=None):
	"""Direct document access guard (/app/item/ITEM-X, frappe.get_doc)."""
	if not user:
		user = frappe.session.user

	if ptype in ("create", "write", "delete") and ptype != "read":
		# create/edit is further guarded by check_item_create_permission
		# in the Item doc_events; read access is what we enforce here.
		pass

	if _user_has_full_visibility(user):
		return True

	# read / select / email / print etc. - apply the operational rule
	if int(doc.get("is_fixed_asset") or 0) == 0 and (
		int(doc.get("is_sales_item") or 0) == 1
		or int(doc.get("is_purchase_item") or 0) == 1
	):
		return True

	return False
