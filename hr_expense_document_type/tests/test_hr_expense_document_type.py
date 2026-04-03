import base64

from odoo import fields
from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("-at_install", "post_install")
class TestHrExpenseDocumentType(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.misc_journal = cls.company_data["default_journal_misc"]
        cls.env["ir.config_parameter"].sudo().set_param(
            "hr_expense.entry_journal_id", cls.misc_journal.id
        )

    def _create_expense(self, document_type="invoice", amount=100.0):
        return self.env["hr.expense"].create(
            {
                "name": f"Expense {document_type}",
                "employee_id": self.expense_employee.id,
                "product_id": self.product_zero_cost.id,
                "total_amount": amount,
                "expense_document_type": document_type,
                "payment_mode": "own_account",
            }
        )

    def _create_invoice_expense(
        self,
        amount=100.0,
        partner=None,
        number=None,
        invoice_date=None,
        accounting_date=None,
    ):
        vals = {
            "name": "Invoice Expense",
            "employee_id": self.expense_employee.id,
            "product_id": self.product_zero_cost.id,
            "total_amount": amount,
            "expense_document_type": "invoice",
            "payment_mode": "own_account",
        }
        if partner:
            vals["invoice_partner_id"] = partner.id
        if number:
            vals["invoice_number"] = number
        if invoice_date:
            vals["invoice_date_manual"] = invoice_date
        if accounting_date:
            vals["invoice_accounting_date"] = accounting_date
        return self.env["hr.expense"].create(vals)

    def test_split_sheet_values_by_document_type(self):
        expense_invoice = self._create_expense(document_type="invoice", amount=120.0)
        expense_entry = self._create_expense(document_type="entry", amount=80.0)

        values = (expense_invoice + expense_entry)._get_default_expense_sheet_values()
        self.assertEqual(len(values), 2)

        sheet_line_sets = {
            tuple(command[2])
            for vals in values
            for command in vals["expense_line_ids"]
            if command[0] == 6
        }
        self.assertIn((expense_invoice.id,), sheet_line_sets)
        self.assertIn((expense_entry.id,), sheet_line_sets)

    def test_entry_flow_creates_misc_entry(self):
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Entry Sheet",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Entry Expense",
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_zero_cost.id,
                            "total_amount": 150.0,
                            "expense_document_type": "entry",
                        },
                    )
                ],
            }
        )

        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.action_sheet_move_create()

        self.assertEqual(sheet.state, "post")
        self.assertEqual(sheet.account_move_id.move_type, "entry")
        self.assertEqual(sheet.account_move_id.journal_id, self.misc_journal)
        self.assertTrue(sheet.account_move_id.ref.startswith("GASTOS "))

        payable_lines = sheet.account_move_id.line_ids.filtered(
            lambda line: line.account_type == "liability_payable"
        )
        self.assertTrue(payable_lines)
        self.assertTrue(any(line.expense_id for line in payable_lines))

    def test_invoice_attachments_copied_without_duplicates(self):
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Invoice Sheet",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Invoice Expense",
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_zero_cost.id,
                            "total_amount": 90.0,
                            "expense_document_type": "invoice",
                        },
                    )
                ],
            }
        )
        expense = sheet.expense_line_ids

        payload = base64.b64encode(b"same-pdf-content")
        self.env["ir.attachment"].create(
            {
                "name": "ticket.pdf",
                "datas": payload,
                "mimetype": "application/pdf",
                "res_model": "hr.expense",
                "res_id": expense.id,
            }
        )
        self.env["ir.attachment"].create(
            {
                "name": "ticket.pdf",
                "datas": payload,
                "mimetype": "application/pdf",
                "res_model": "hr.expense",
                "res_id": expense.id,
            }
        )

        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.action_sheet_move_create()

        self.assertEqual(sheet.account_move_id.state, "draft")
        self.assertEqual(
            sheet.account_move_id.ref,
            f"@gastos {self.expense_employee.name} con factura",
        )
        move_attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", sheet.account_move_id.id)]
        )
        self.assertEqual(len(move_attachments), 1)

    def test_invoice_flow_maps_invoice_fields_to_move(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor Factura",
                "supplier_rank": 1,
            }
        )
        invoice_date = fields.Date.to_date("2026-03-10")
        accounting_date = fields.Date.to_date("2026-03-12")
        expense = self._create_invoice_expense(
            amount=140.0,
            partner=partner,
            number="FAC-2026-001",
            invoice_date=invoice_date,
            accounting_date=accounting_date,
        )

        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Invoice Sheet Mapped",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [(6, 0, [expense.id])],
            }
        )

        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.action_sheet_move_create()

        self.assertEqual(sheet.account_move_id.move_type, "in_invoice")
        self.assertEqual(sheet.account_move_id.partner_id, partner)
        self.assertEqual(sheet.account_move_id.commercial_partner_id, partner.commercial_partner_id)
        self.assertEqual(sheet.account_move_id.ref, "FAC-2026-001")
        self.assertEqual(sheet.account_move_id.invoice_date, invoice_date)
        self.assertEqual(sheet.account_move_id.date, accounting_date)

    def test_invoice_flow_without_extra_data_keeps_legacy_behavior(self):
        expense = self._create_invoice_expense(amount=110.0)
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Invoice Sheet Legacy",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [(6, 0, [expense.id])],
            }
        )

        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.action_sheet_move_create()

        self.assertEqual(
            sheet.account_move_id.ref,
            f"@gastos {self.expense_employee.name} con factura",
        )

    def test_split_sheet_values_by_invoice_partner_and_number(self):
        partner_a = self.env["res.partner"].create({"name": "Proveedor A", "supplier_rank": 1})
        partner_b = self.env["res.partner"].create({"name": "Proveedor B", "supplier_rank": 1})
        expense_1 = self._create_invoice_expense(partner=partner_a, number="F-001", amount=50.0)
        expense_2 = self._create_invoice_expense(partner=partner_a, number="F-001", amount=60.0)
        expense_3 = self._create_invoice_expense(partner=partner_a, number="F-002", amount=70.0)
        expense_4 = self._create_invoice_expense(partner=partner_b, number="F-001", amount=80.0)

        values = (expense_1 + expense_2 + expense_3 + expense_4)._get_default_expense_sheet_values()

        self.assertEqual(len(values), 3)
        line_groups = sorted(
            sorted(command[2])
            for vals in values
            for command in vals["expense_line_ids"]
            if command[0] == 6
        )
        self.assertEqual(
            line_groups,
            sorted(
                [
                    sorted([expense_1.id, expense_2.id]),
                    [expense_3.id],
                    [expense_4.id],
                ]
            ),
        )
