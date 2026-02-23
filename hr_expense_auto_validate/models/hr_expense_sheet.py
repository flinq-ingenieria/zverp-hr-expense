from odoo import models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _auto_validate_mail_suppression_context(self):
        return {
            "default_notify": False,
            "mail_auto_subscribe_no_notify": True,
            "mail_notify_force_send": False,
            "mail_post_autofollow": False,
            "tracking_disable": True,
        }

    def action_submit_sheet(self):
        """Submit, auto-approve and post accounting entries."""
        sheets = self.sudo().with_context(
            **self._auto_validate_mail_suppression_context()
        )
        result = super(HrExpenseSheet, sheets).action_submit_sheet()
        sheets._do_approve()
        approved_sheets = sheets.filtered(lambda sheet: sheet.state == "approve")
        if approved_sheets:
            approved_sheets.action_sheet_move_create()
        return result
