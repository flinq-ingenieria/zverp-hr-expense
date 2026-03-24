from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("-at_install", "post_install")
class TestHrExpenseAutoValidate(TestExpenseCommon):
    def test_auto_process_enabled_submits_and_posts(self):
        self.env.company.expense_auto_process_enabled = True
        self.addCleanup(self.env.company.write, {"expense_auto_process_enabled": False})
        self.env["ir.config_parameter"].sudo().set_param("hr_expense.entry_journal_id", self.company_data["default_journal_misc"].id)

        sheet = self.env["hr.expense.sheet"].with_user(self.expense_user_employee).create(
            {
                "name": "Auto Sheet",
                "employee_id": self.expense_employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "expense_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Auto Entry Expense",
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_zero_cost.id,
                            "total_amount": 75.0,
                            "expense_document_type": "entry",
                        },
                    )
                ],
            }
        )

        sheet.with_user(self.expense_user_employee).action_submit_sheet()

        self.assertEqual(sheet.state, "post")
        self.assertTrue(sheet.account_move_id)
        self.assertEqual(sheet.account_move_id.move_type, "entry")
