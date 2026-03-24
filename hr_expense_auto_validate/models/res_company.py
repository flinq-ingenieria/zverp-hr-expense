from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    expense_auto_process_enabled = fields.Boolean(
        string="Auto-validate employee expenses",
        help="When enabled, submitting an expense report will auto-approve and create accounting documents.",
    )
