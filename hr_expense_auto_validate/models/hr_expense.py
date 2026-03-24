from odoo import _, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    def action_submit_expenses(self):
        """Skip draft report step when auto-process is enabled for the company."""
        if len(self.company_id) != 1 or not self.company_id.expense_auto_process_enabled:
            return super().action_submit_expenses()

        context_vals = self._get_default_expense_sheet_values()
        sheets = self.env["hr.expense.sheet"].create(context_vals)
        sheets.action_submit_sheet()

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
            "target": "current",
            "res_id": sheets.id,
        }


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _is_auto_process_enabled(self):
        self.ensure_one()
        return bool(self.company_id.expense_auto_process_enabled)

    def action_submit_sheet(self):
        result = super().action_submit_sheet()

        if not self._is_auto_process_enabled():
            return result

        for sheet in self.filtered(lambda s: s.state == "submit"):
            sheet = sheet.sudo()
            sheet._validate_analytic_distribution()
            sheet._do_approve()
            if sheet.state == "approve":
                sheet.action_sheet_move_create()

        return result
