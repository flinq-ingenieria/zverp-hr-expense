from odoo import _, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    def _auto_validate_mail_suppression_context(self):
        return {
            "default_notify": False,
            "mail_auto_subscribe_no_notify": True,
            "mail_notify_force_send": False,
            "mail_post_autofollow": False,
            "tracking_disable": True,
        }

    def action_submit_expenses(self):
        """Create report(s) and trigger auto submit/approve/post flow."""
        context_vals = self._get_default_expense_sheet_values()
        sheets = self.env["hr.expense.sheet"].create(context_vals)
        sheets.sudo().with_context(
            **self._auto_validate_mail_suppression_context()
        ).action_submit_sheet()

        if len(sheets) > 1:
            return {
                "name": _("Expense Reports"),
                "type": "ir.actions.act_window",
                "views": [[False, "list"], [False, "form"]],
                "res_model": "hr.expense.sheet",
                "domain": [("id", "in", sheets.ids)],
                "context": self.env.context,
            }

        return {
            "name": _("Expense Report"),
            "type": "ir.actions.act_window",
            "views": [[False, "form"]],
            "res_model": "hr.expense.sheet",
            "res_id": sheets.id,
            "target": "current",
            "context": self.env.context,
        }
