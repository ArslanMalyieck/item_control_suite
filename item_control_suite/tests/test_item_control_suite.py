# Copyright (c) 2026, BOT Solutions
# License: MIT. See license.txt

import json

import frappe
import frappe.desk.search as search
from frappe.tests.utils import FrappeTestCase

from item_control_suite.install import seed_test_items


def _set_user(email):
	frappe.set_user(email)


def _ensure_test_user(email, first_name, roles):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
			}
		)
	user.roles = []
	for role in roles:
		user.append("roles", {"role": role})
	user.flags.ignore_permissions = True
	user.save(ignore_permissions=True)
	frappe.utils.password.update_password(email, "Test@12345")
	return user


def _ensure_role(role_name):
	if frappe.db.exists("Role", role_name):
		return
	frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
		ignore_permissions=True
	)


class BaseTestSetup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		_ensure_role("Item Master Allow")
		# restricted user needs a standard role that grants Item read
		# (e.g. Stock User) for the permission-query path to be exercised
		_ensure_test_user("ics.user.allow@test.com", "ICS Allow", ["Item Master Allow"])
		_ensure_test_user("ics.user.restricted@test.com", "ICS Restricted", ["Stock User"])
		_ensure_test_user("ics.user.manager@test.com", "ICS Manager", ["Item Manager"])
		seed_test_items()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def tearDown(self):
		# make sure no stale request context leaks between tests
		frappe.local.form_dict.pop("filters", None)
		frappe.set_user("Administrator")
		super().tearDown()


class TestPurchaseInvoiceAmount(BaseTestSetup):
	def test_custom_field_exists(self):
		meta = frappe.get_meta("Purchase Invoice Item")
		self.assertTrue(meta.has_field("custom_input_amount"), "custom_input_amount missing")
		df = meta.get_field("custom_input_amount")
		self.assertEqual(df.fieldtype, "Currency")
		self.assertEqual(df.label, "Amount")

	def _make_pi(self, rows):
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = "Test Supplier"
		pi.company = frappe.db.get_single_value("Global Defaults", "default_company")
		for r in rows:
			pi.append(
				"items",
				{
					"item_code": r["item_code"],
					"qty": r.get("qty", 1),
					"custom_input_amount": r.get("amount", 0),
					"rate": r.get("rate", 0),
				},
			)
		return pi

	def test_qty_amount_calculates_rate(self):
		pi = self._make_pi([{"item_code": "TEST-BUY-001", "qty": 10, "amount": 1000}])
		pi.flags.ignore_permissions = True
		pi.save()
		self.assertAlmostEqual(pi.items[0].rate, 100, places=4)
		self.assertAlmostEqual(pi.items[0].amount, 1000, places=2)

	def test_second_calculation(self):
		pi = self._make_pi([{"item_code": "TEST-BUY-001", "qty": 5, "amount": 1250}])
		pi.flags.ignore_permissions = True
		pi.save()
		self.assertAlmostEqual(pi.items[0].rate, 250, places=4)
		self.assertAlmostEqual(pi.items[0].amount, 1250, places=2)

	def test_zero_qty_no_division_error(self):
		# ERPNext itself rejects qty=0 on save (InvalidQtyError). The hook
		# must never raise ZeroDivisionError - exercise it in isolation.
		from item_control_suite.purchase_invoice import derive_rate_from_input_amount

		pi = self._make_pi([{"item_code": "TEST-BUY-001", "qty": 0, "amount": 1000}])
		derive_rate_from_input_amount(pi, None)
		self.assertEqual(pi.items[0].rate, 0)
		# and the standard guard still applies on save
		pi.flags.ignore_permissions = True
		with self.assertRaises(Exception) as ctx:
			pi.save()
		self.assertNotIsInstance(ctx.exception, ZeroDivisionError)

	def test_multiple_rows_independent(self):
		pi = self._make_pi(
			[
				{"item_code": "TEST-BUY-001", "qty": 10, "amount": 1000},
				{"item_code": "TEST-BOTH-001", "qty": 4, "amount": 80},
			]
		)
		pi.flags.ignore_permissions = True
		pi.save()
		self.assertAlmostEqual(pi.items[0].rate, 100, places=4)
		self.assertAlmostEqual(pi.items[0].amount, 1000, places=2)
		self.assertAlmostEqual(pi.items[1].rate, 20, places=4)
		self.assertAlmostEqual(pi.items[1].amount, 80, places=2)

	def test_standard_submit_not_broken(self):
		pi = self._make_pi([{"item_code": "TEST-BUY-001", "qty": 2, "amount": 60}])
		pi.flags.ignore_permissions = True
		pi.save()
		pi.submit()
		self.assertEqual(pi.docstatus, 1)
		self.assertAlmostEqual(pi.items[0].amount, 60, places=2)

	def test_rate_and_amount_readonly(self):
		for field in ("rate", "amount"):
			self.assertTrue(
				frappe.db.exists(
					"Property Setter",
					{
						"doc_type": "Purchase Invoice Item",
						"field_name": field,
						"property": "read_only",
						"value": 1,
					},
				),
				f"{field} should be read-only",
			)

	def test_add_and_delete_rows_no_break(self):
		# start with two rows
		pi = self._make_pi(
			[
				{"item_code": "TEST-BUY-001", "qty": 10, "amount": 1000},
				{"item_code": "TEST-BOTH-001", "qty": 4, "amount": 80},
			]
		)
		pi.flags.ignore_permissions = True
		pi.save()
		self.assertAlmostEqual(pi.items[0].amount, 1000, places=2)
		self.assertAlmostEqual(pi.items[1].amount, 80, places=2)

		# add a third row, save again
		pi.append(
			"items",
			{
				"item_code": "TEST-BUY-001",
				"qty": 2,
				"custom_input_amount": 50,
			},
		)
		pi.save()
		self.assertEqual(len(pi.items), 3)
		self.assertAlmostEqual(pi.items[2].rate, 25, places=4)
		self.assertAlmostEqual(pi.items[2].amount, 50, places=2)
		# existing rows untouched
		self.assertAlmostEqual(pi.items[0].amount, 1000, places=2)
		self.assertAlmostEqual(pi.items[1].amount, 80, places=2)

		# delete the second row, save again
		pi.items.remove(pi.items[1])
		pi.save()
		self.assertEqual(len(pi.items), 2)
		self.assertAlmostEqual(pi.items[0].amount, 1000, places=2)
		self.assertAlmostEqual(pi.items[1].amount, 50, places=2)

		# submit still works
		pi.submit()
		self.assertEqual(pi.docstatus, 1)


class TestVisibility(BaseTestSetup):
	def _item_list(self, user, workspace=None):
		"""workspace: None | 'sales' | 'buying' | 'asset' - emulates the
		workspace page request context (a protected flag filter)."""
		_set_user(user)
		filters = {}
		if workspace == "sales":
			filters = {"is_sales_item": 1}
		elif workspace == "buying":
			filters = {"is_purchase_item": 1}
		elif workspace == "asset":
			filters = {"is_fixed_asset": 1}

		frappe.local.form_dict["filters"] = json.dumps(
			[[frappe._dict({"Item": f"value"}), 0, 0]] if False else []
		)
		if workspace:
			field = {"sales": "is_sales_item", "buying": "is_purchase_item", "asset": "is_fixed_asset"}[workspace]
			frappe.local.form_dict["filters"] = json.dumps([["Item", field, "=", 1]])
		else:
			frappe.local.form_dict["filters"] = json.dumps([])

		try:
			return frappe.get_list(
				"Item",
				filters=filters,
				fields=["name"],
				ignore_permissions=False,
				limit_page_length=200,
			)
		finally:
			frappe.set_user("Administrator")

	def test_sales_items_only_sales(self):
		names = {r["name"] for r in self._item_list("ics.user.restricted@test.com", "sales")}
		self.assertIn("TEST-SALES-001", names)
		self.assertIn("TEST-BOTH-001", names)
		self.assertNotIn("TEST-BUY-001", names)
		self.assertNotIn("TEST-HIDDEN-001", names)
		self.assertNotIn("TEST-ASSET-001", names)

	def test_buying_items_only_purchase(self):
		names = {r["name"] for r in self._item_list("ics.user.restricted@test.com", "buying")}
		self.assertIn("TEST-BUY-001", names)
		self.assertIn("TEST-BOTH-001", names)
		self.assertNotIn("TEST-SALES-001", names)
		self.assertNotIn("TEST-HIDDEN-001", names)
		self.assertNotIn("TEST-ASSET-001", names)

	def test_asset_items_only_fixed_asset(self):
		names = {r["name"] for r in self._item_list("ics.user.restricted@test.com", "asset")}
		self.assertIn("TEST-ASSET-001", names)
		self.assertNotIn("TEST-SALES-001", names)
		self.assertNotIn("TEST-BUY-001", names)
		self.assertNotIn("TEST-HIDDEN-001", names)

	def test_hidden_item_not_in_default_list(self):
		names = {r["name"] for r in self._item_list("ics.user.restricted@test.com")}
		self.assertNotIn("TEST-HIDDEN-001", names)
		self.assertNotIn("TEST-ASSET-001", names)
		self.assertIn("TEST-SALES-001", names)
		self.assertIn("TEST-BUY-001", names)

	def test_allow_sees_everything(self):
		names = {r["name"] for r in self._item_list("ics.user.allow@test.com")}
		self.assertIn("TEST-HIDDEN-001", names)
		self.assertIn("TEST-ASSET-001", names)
		self.assertIn("TEST-SALES-001", names)
		self.assertIn("TEST-BUY-001", names)

	def test_direct_document_access_denied_for_hidden(self):
		_set_user("ics.user.restricted@test.com")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc("Item", "TEST-HIDDEN-001", check_permission=True)
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc("Item", "TEST-ASSET-001", check_permission=True)
			doc = frappe.get_doc("Item", "TEST-SALES-001", check_permission=True)
			self.assertEqual(doc.item_code, "TEST-SALES-001")
		finally:
			frappe.set_user("Administrator")

	def test_link_search_respects_visibility(self):
		_set_user("ics.user.restricted@test.com")
		try:
			results = search.search_link(doctype="Item", txt="TEST", page_length=50)
			names = [r.get("value") for r in results]
			self.assertIn("TEST-SALES-001", names)
			self.assertIn("TEST-BUY-001", names)
			self.assertNotIn("TEST-HIDDEN-001", names)
			self.assertNotIn("TEST-ASSET-001", names)
		finally:
			frappe.set_user("Administrator")

	def test_search_widget_respects_visibility(self):
		_set_user("ics.user.restricted@test.com")
		try:
			results = search.search_widget(doctype="Item", txt="TEST", page_length=50)
			names = [r[0] for r in results]
			self.assertIn("TEST-SALES-001", names)
			self.assertNotIn("TEST-HIDDEN-001", names)
			self.assertNotIn("TEST-ASSET-001", names)
		finally:
			frappe.set_user("Administrator")

	def test_allow_can_search_everything(self):
		_set_user("ics.user.allow@test.com")
		try:
			results = search.search_link(doctype="Item", txt="TEST", page_length=50)
			names = [r.get("value") for r in results]
			self.assertIn("TEST-HIDDEN-001", names)
			self.assertIn("TEST-ASSET-001", names)
		finally:
			frappe.set_user("Administrator")


class TestCreationPermission(BaseTestSetup):
	def test_item_manager_can_create(self):
		_set_user("ics.user.manager@test.com")
		try:
			doc = frappe.new_doc("Item")
			doc.item_code = "TEST-CREATE-MGR-001"
			doc.item_name = "Mgr Created"
			doc.item_group = "Products"
			doc.stock_uom = "Nos"
			doc.is_stock_item = 0
			doc.insert(ignore_permissions=False)
			self.assertEqual(doc.item_code, "TEST-CREATE-MGR-001")
		finally:
			frappe.set_user("Administrator")

	def test_restricted_user_cannot_create(self):
		_set_user("ics.user.restricted@test.com")
		try:
			doc = frappe.new_doc("Item")
			doc.item_code = "TEST-CREATE-NO-001"
			doc.item_name = "No Create"
			doc.item_group = "Products"
			doc.stock_uom = "Nos"
			doc.is_stock_item = 0
			with self.assertRaises(frappe.PermissionError):
				doc.insert(ignore_permissions=False)
		finally:
			frappe.set_user("Administrator")
