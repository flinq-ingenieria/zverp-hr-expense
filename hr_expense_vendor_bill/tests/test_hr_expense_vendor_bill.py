import base64

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("-at_install", "post_install")
class TestHrExpenseVendorBill(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.misc_journal = cls.company_data["default_journal_misc"]
        cls.env["ir.config_parameter"].sudo().set_param("hr_expense.entry_journal_id", cls.misc_journal.id)

    def _create_invoice_expense(self, amount=100.0, payment_mode="own_account", partner=None, number=None):
        vals = {
            "name": "Invoice Expense",
            "employee_id": self.expense_employee.id,
            "product_id": self.product_zero_cost.id,
            "total_amount": amount,
            "expense_document_type": "invoice",
            "payment_mode": payment_mode,
        }
        if partner:
            vals["invoice_partner_id"] = partner.id
        if number:
            vals["invoice_number"] = number
        return self.env["hr.expense"].create(vals)

    def test_invoice_own_account_creates_draft_vendor_bill_with_attachment(self):
        partner = self.env["res.partner"].create({"name": "Proveedor OA", "supplier_rank": 1})
        expense = self._create_invoice_expense(partner=partner, number="OA-001")
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Invoice Own Account",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [(6, 0, [expense.id])],
            }
        )

        payload = base64.b64encode(b"invoice-content")
        self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "datas": payload,
                "mimetype": "application/pdf",
                "res_model": "hr.expense",
                "res_id": expense.id,
            }
        )

        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.action_sheet_move_create()

        self.assertEqual(sheet.account_move_id.move_type, "in_invoice")
        self.assertEqual(sheet.account_move_id.state, "draft")
        self.assertEqual(sheet.account_move_id.partner_id, partner)
        self.assertEqual(sheet.account_move_id.ref, "OA-001")

        move_attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", sheet.account_move_id.id)]
        )
        self.assertEqual(len(move_attachments), 1)
        self.assertEqual(
            sheet.account_move_id.message_main_attachment_id,
            move_attachments,
            "The copied attachment must be set as main attachment so 'Print Original Bills' can find it.",
        )

    def test_invoice_company_account_creates_draft_vendor_bill_without_payment(self):
        partner = self.env["res.partner"].create({"name": "Proveedor CA", "supplier_rank": 1})
        expense = self._create_invoice_expense(
            amount=180.0,
            payment_mode="company_account",
            partner=partner,
            number="CA-001",
        )
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Invoice Company Account",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "bank_journal_id": self.company_data["default_journal_bank"].id,
                "expense_line_ids": [(6, 0, [expense.id])],
            }
        )

        self.assertTrue(sheet.use_invoice_journal)
        self.assertEqual(sheet.journal_displayed_id, self.company_data["default_journal_purchase"])

        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.action_sheet_move_create()

        self.assertEqual(sheet.account_move_id.move_type, "in_invoice")
        self.assertEqual(sheet.account_move_id.state, "draft")
        self.assertEqual(sheet.account_move_id.ref, "CA-001")
        self.assertEqual(sheet.account_move_id.journal_id, self.company_data["default_journal_purchase"])

        payments = self.env["account.payment"].search([("expense_sheet_id", "=", sheet.id)])
        self.assertFalse(payments)

    def test_invoice_requires_supplier_and_number_before_submit(self):
        expense = self._create_invoice_expense(amount=90.0)

        with self.assertRaises(UserError):
            expense.action_submit_expenses()

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

    def test_entry_payment_state_reflects_reconciliation(self):
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Entry Sheet Payment",
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

        self.assertEqual(sheet.account_move_id.payment_state, "not_paid")
        self.assertEqual(sheet.payment_state, "not_paid")

        payment_register = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=sheet.account_move_id.ids
        ).create({})
        payment_register._create_payments()

        self.assertEqual(sheet.account_move_id.payment_state, "paid")
        self.assertEqual(sheet.payment_state, "paid")

        with self.assertRaises(UserError):
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=sheet.account_move_id.ids
            ).create({})

    def test_standard_approval_flow_is_kept(self):
        partner = self.env["res.partner"].create({"name": "Proveedor Approvals", "supplier_rank": 1})
        expense = self._create_invoice_expense(partner=partner, number="AP-001")
        sheet = self.env["hr.expense.sheet"].create(
            {
                "name": "Approval Flow",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [(6, 0, [expense.id])],
            }
        )

        sheet.action_submit_sheet()
        self.assertEqual(sheet.state, "submit")
