from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    expense_default_document_type = fields.Selection(
        selection=[("entry", "Gasto"), ("invoice", "Factura")],
        string="Default Expense Document Type",
        default="entry",
        required=True,
        help="Default document type used when creating new expenses.",
    )
