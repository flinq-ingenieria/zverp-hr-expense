from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    expense_default_document_type = fields.Selection(
        string="Default Expense Document Type",
        related="company_id.expense_default_document_type",
        readonly=False,
    )
    expense_entry_journal_id = fields.Many2one(
        "account.journal",
        string="Expense Entry Journal",
        domain="[('type', '=', 'general')]",
        config_parameter="hr_expense.entry_journal_id",
        help="Miscellaneous journal used for expense lines of type 'Gasto'.",
    )
