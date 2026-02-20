from odoo import models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def action_submit_sheet(self):
        """Submit, auto-approve and post accounting entries."""
        result = super().action_submit_sheet()
        sheets = self.sudo()
        sheets._do_approve()
        approved_sheets = sheets.filtered(lambda sheet: sheet.state == "approve")
        if approved_sheets:
            approved_sheets.action_sheet_move_create()
        return result
