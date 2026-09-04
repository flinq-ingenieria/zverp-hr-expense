from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_expense_entry_payment_state(self):
        self.ensure_one()
        if self.state != "posted":
            return "not_paid"

        payable_lines = self.line_ids.filtered(
            lambda line: line.account_type in ("asset_receivable", "liability_payable")
        )
        if not payable_lines:
            return "not_paid"

        currency = self.company_id.currency_id
        total_balance = sum(payable_lines.mapped("balance"))
        total_residual = sum(payable_lines.mapped("amount_residual"))

        if currency.is_zero(total_residual):
            return "paid"
        if currency.is_zero(total_residual - total_balance):
            return "not_paid"
        return "partial"

    def _compute_payment_state(self):
        entry_expense_moves = self.filtered(
            lambda move: move.move_type == "entry" and move.expense_sheet_id.payment_mode == "own_account"
        )
        super(AccountMove, self - entry_expense_moves)._compute_payment_state()
        for move in entry_expense_moves:
            move.payment_state = move._get_expense_entry_payment_state()
