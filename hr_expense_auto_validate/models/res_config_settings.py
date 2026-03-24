from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    expense_auto_process_enabled = fields.Boolean(
        string="Auto-validate employee expenses",
        related="company_id.expense_auto_process_enabled",
        readonly=False,
        help="When enabled, submitting an expense report will auto-approve and create accounting documents.",
    )
