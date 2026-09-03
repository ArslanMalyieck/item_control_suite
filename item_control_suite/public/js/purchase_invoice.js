// Purchase Invoice - Amount based pricing (client side helper).
//
// When the user enters Qty and the custom Amount (custom_input_amount),
// the standard Rate is derived immediately (Amount / Qty) so ERPNext's
// normal amount = qty * rate is visible instantly. The authoritative
// derivation is repeated server-side in before_validate
// (item_control_suite.purchase_invoice.derive_rate_from_input_amount)
// so this JS is only a UX helper, never a security boundary.
//
// Rounding is done with flt(value, 6) to keep the UI in sync with the
// server (rate precision 6). No unsafe float math is persisted.

frappe.ui.form.on("Purchase Invoice Item", {
	qty(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		_derive_rate(row, cdt, cdn);
	},
	custom_input_amount(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		_derive_rate(row, cdt, cdn);
	},
});

function _derive_rate(row, cdt, cdn) {
	const qty = flt(row.qty);
	const amount = flt(row.custom_input_amount);
	if (qty > 0 && amount > 0) {
		frappe.model.set_value(cdt, cdn, "rate", flt(amount / qty, 6));
	}
}
