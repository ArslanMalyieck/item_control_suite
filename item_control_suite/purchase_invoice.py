import frappe
from frappe.utils import flt

# ============================================================
# PURCHASE INVOICE - AMOUNT BASED PRICING
# ============================================================
# Workflow: user selects item, enters Qty, then enters the custom
# "Amount" (custom_input_amount). The standard rate is derived as
#   rate = custom_input_amount / qty
# and ERPNext's own calculation then produces
#   amount = qty * rate == custom_input_amount
#
# The hook runs on before_validate so the derived rate is in place
# before ERPNext computes the standard amount - no override of
# ERPNext's own validate/submit logic is needed.
#
# Safety:
#   - qty <= 0  -> no derivation (no division by zero)
#   - amount <= 0 -> treat as "not set"; standard rate/amount flow
#     is left untouched (no stale values are written)
#   - multiple rows are processed independently
#   - rounding uses flt with a rate precision of 6 decimals and the
#     final ERPNext amount is rounded by ERPNext itself to the
#     currency precision, so 1000/10 = 100 etc. always matches
# ============================================================

RATE_PRECISION = 6


def derive_rate_from_input_amount(doc, method=None):
	for item in doc.items or []:
		qty = flt(item.qty)
		amount = flt(item.custom_input_amount)

		if qty > 0 and amount > 0:
			item.rate = flt(amount / qty, RATE_PRECISION)
