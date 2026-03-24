import base64

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
