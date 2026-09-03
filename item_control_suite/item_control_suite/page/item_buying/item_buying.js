frappe.pages["item-buying"].on_page_load = function (wrapper) {
	frappe.route_options = { item_type: "buying", is_purchase_item: 1 };
	frappe.set_route("List", "Item");
};
