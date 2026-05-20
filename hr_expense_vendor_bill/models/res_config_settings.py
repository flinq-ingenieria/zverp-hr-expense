from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    expense_entry_journal_id = fields.Many2one(
        "account.journal",
        string="Expense Entry Journal",
        domain="[('type', '=', 'general')]",
        config_parameter="hr_expense.entry_journal_id",
        help="Miscellaneous journal used for expense lines of type 'Entry'.",
    )
