frappe.pages["item-asset"].on_page_load = function (wrapper) {
	frappe.route_options = { item_type: "asset", is_fixed_asset: 1 };
	frappe.set_route("List", "Item");
};
