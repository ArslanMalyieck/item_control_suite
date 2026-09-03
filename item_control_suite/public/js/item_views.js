// Item list view behaviour for the specialised workspace views.
//
// The workspace pages navigate with frappe.route_options carrying the
// real flag (e.g. { is_fixed_asset: 1 }) plus an internal item_type.
// Frappe's CORE list view consumes route_options in before_refresh and
// applies the flag as a standard filter - the URL therefore shows the
// real filter (?is_fixed_asset=1) and the request carries the flag, which
// the server (item_control_suite.item_visibility) turns into the SQL
// workspace rule. No request-wrapper hacks are used, so a cached list
// instance can never leak a stale filter.
//
// This file only:
//   1. sets the page title (Sales Items / Buying Items / Asset Items)
//   2. on plain Item lists (no context), removes any stale chips on the
//      protected fields that were persisted in user settings - they must
//      never silently turn a direct list into a workspace view
//
// It deliberately does NOT clear route_options (the core applies them)
// and does NOT wrap get_call_args (no hidden injection needed).

const __ics_base_settings = frappe.listview_settings["Item"] || {};
const __ics_base_onload = __ics_base_settings.onload;

frappe.listview_settings["Item"] = Object.assign({}, __ics_base_settings, {
	onload(listview) {
		if (__ics_base_onload) {
			__ics_base_onload(listview);
		}

		const opts = frappe.route_options || {};
		const has_context = !!(opts.item_type || opts.is_sales_item === 1 || opts.is_purchase_item === 1 || opts.is_fixed_asset === 1);

		try {
			if (!has_context) {
				// plain Item list: drop any stale protected-field chips
				["is_sales_item", "is_purchase_item", "is_fixed_asset"].forEach((field) => {
					listview.filter_area.remove(field);
				});
				return;
			}

			let title = null;
			if (opts.item_type === "sales" || opts.is_sales_item === 1) title = "Sales Items";
			else if (opts.item_type === "buying" || opts.is_purchase_item === 1) title = "Buying Items";
			else if (opts.item_type === "asset" || opts.is_fixed_asset === 1) title = "Asset Items";

			if (title) {
				listview.page.set_title(title);
			}
		} catch (e) {
			console.error("item_control_suite list onload error:", e);
		}
	},
});
