frappe.pages["item-sales"].on_page_load = function (wrapper) {
	frappe.route_options = { item_type: "sales", is_sales_item: 1 };
	frappe.set_route("List", "Item");
};
