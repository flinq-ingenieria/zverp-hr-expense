from odoo import models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def action_submit_sheet(self):
        """Submit and auto-approve expense sheets."""
        result = super().action_submit_sheet()
        self.sudo()._do_approve()
        return result
