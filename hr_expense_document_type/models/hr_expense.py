from odoo import _, Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from odoo.tools.misc import clean_context, format_date


ENTRY_JOURNAL_PARAM = "hr_expense.entry_journal_id"


class HrExpense(models.Model):
    _inherit = "hr.expense"

    expense_document_type = fields.Selection(
        selection=[("invoice", "Factura"), ("entry", "Gasto")],
        string="Tipo de documento",
        default="entry",
        required=True,
        tracking=True,
        states={"done": [("readonly", True)], "approved": [("readonly", True)], "reported": [("readonly", True)]},
        help="Factura: crea factura proveedor. Gasto: crea asiento contable en diario miscelaneo.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("expense_document_type"):
                continue
            company = (
                self.env["res.company"].browse(vals["company_id"])
                if vals.get("company_id")
                else self.env.company
            )
            vals["expense_document_type"] = company.sudo().expense_default_document_type or "entry"
        return super().create(vals_list)

    def _get_default_expense_sheet_values(self):
        # If there is an expense with total_amount_company == 0, it means that expense has not been processed by OCR yet
        expenses_with_amount = self.filtered(
            lambda expense: not float_is_zero(
                expense.total_amount_company,
                precision_rounding=expense.company_currency_id.rounding,
            )
        )

        if any(expense.state != "draft" or expense.sheet_id for expense in expenses_with_amount):
            raise UserError(_("You cannot report twice the same line!"))
        if not expenses_with_amount:
            raise UserError(_("You cannot report the expenses without amount!"))
        if len(self.company_id) != 1:
            raise UserError(_("You cannot report expenses for different companies in the same report."))
        if len(expenses_with_amount.mapped("employee_id")) != 1:
            raise UserError(_("You cannot report expenses for different employees in the same report."))
        if any(not expense.product_id for expense in expenses_with_amount):
            raise UserError(_("You can not create report without category."))

        grouped_expenses = {}
        for expense in expenses_with_amount:
            doc_type_key = (
                expense.expense_document_type
                if expense.payment_mode == "own_account"
                else "invoice"
            )
            key = (expense.payment_mode, doc_type_key)
            grouped_expenses.setdefault(key, self.env["hr.expense"])
            grouped_expenses[key] |= expense

        values = []
        for (payment_mode, doc_type), todo in grouped_expenses.items():
            paid_by = "company" if payment_mode == "company_account" else "employee"
            doc_label = dict(self._fields["expense_document_type"].selection).get(doc_type, doc_type)

            if len(grouped_expenses) > 1:
                sheet_name = _(
                    "New Expense Report, paid by %(paid_by)s (%(doc_type)s)",
                    paid_by=paid_by,
                    doc_type=doc_label,
                )
            else:
                sheet_name = False

            if len(todo) == 1:
                sheet_name = todo.name
            else:
                dates = todo.mapped("date")
                if False not in dates:
                    min_date = format_date(self.env, min(dates))
                    max_date = format_date(self.env, max(dates))
                    if min_date == max_date:
                        sheet_name = min_date
                    else:
                        sheet_name = _("%(date_from)s - %(date_to)s", date_from=min_date, date_to=max_date)

            values.append(
                {
                    "company_id": self.company_id.id,
                    "employee_id": self[0].employee_id.id,
                    "name": sheet_name,
                    "expense_line_ids": [Command.set(todo.ids)],
                    "state": "draft",
                }
            )
        return values

    def _get_expense_account_destination(self):
        self.ensure_one()
        if self.payment_mode == "company_account":
            return super()._get_expense_account_destination()

        employee = self.employee_id.sudo()
        partner = (
            employee.address_home_id.commercial_partner_id
            or employee.user_partner_id.commercial_partner_id
            or employee.user_id.partner_id.commercial_partner_id
            or self.company_id.partner_id.commercial_partner_id
        ).with_company(self.company_id)
        account_dest = partner.property_account_payable_id or partner.parent_id.property_account_payable_id
        if not account_dest:
            raise UserError(
                _(
                    "No payable account found for employee '%(employee)s' or fallback partner '%(partner)s'.",
                    employee=self.employee_id.name,
                    partner=partner.display_name,
                )
            )
        return account_dest.id


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _get_entry_journal(self):
        self.ensure_one()
        journal_id = self.env["ir.config_parameter"].sudo().get_param(ENTRY_JOURNAL_PARAM)
        if not journal_id:
            return self.env["account.journal"]
        return self.env["account.journal"].browse(int(journal_id)).exists()

    def _is_entry_sheet(self):
        self.ensure_one()
        if self.payment_mode != "own_account":
            return False
        types = self.expense_line_ids.mapped("expense_document_type")
        return len(types) == 1 and types[0] == "entry"

    @api.constrains("expense_line_ids", "payment_mode")
    def _check_expense_document_type(self):
        for sheet in self.filtered(lambda s: s.payment_mode == "own_account"):
            if len(sheet.expense_line_ids.mapped("expense_document_type")) > 1:
                raise ValidationError(_("Expenses in the same report must have the same document type."))

    def _get_entry_reference(self):
        self.ensure_one()
        date_value = (
            self.accounting_date
            or max(self.expense_line_ids.mapped("date"))
            or fields.Date.context_today(self)
        )
        if isinstance(date_value, str):
            date_value = fields.Date.from_string(date_value)
        date_compact = fields.Date.to_string(date_value).replace("-", "")
        return f"GASTOS {self.employee_id.name} {date_compact}"

    def _get_invoice_reference(self):
        self.ensure_one()
        return _("@gastos %(employee)s con factura", employee=self.employee_id.name)

    def _get_employee_fallback_partner(self):
        self.ensure_one()
        employee = self.employee_id.sudo()
        return (
            employee.address_home_id.commercial_partner_id
            or employee.user_partner_id.commercial_partner_id
            or employee.user_id.partner_id.commercial_partner_id
            or self.company_id.partner_id.commercial_partner_id
        ).with_company(self.company_id)

    def _prepare_entry_vals(self):
        self.ensure_one()
        entry_journal = self._get_entry_journal()
        if not entry_journal:
            raise UserError(_("Please set an Expense Entry Journal in Settings."))
        if entry_journal.type != "general":
            raise UserError(_("Expense Entry Journal must be of type Miscellaneous."))
        if entry_journal.company_id != self.company_id:
            raise UserError(_("Expense Entry Journal company must match the expense report company."))

        currency = self.company_id.currency_id
        entry_ref = self._get_entry_reference()
        move_lines = []

        for expense in self.expense_line_ids:
            expense_name = expense.name.split("\n")[0][:64]
            line_name = f"{entry_ref}: {expense_name}"

            tax_data = self.env["account.tax"]._compute_taxes(
                [
                    expense._convert_to_tax_base_line_dict(
                        price_unit=expense.total_amount_company,
                        currency=currency,
                    )
                ]
            )
            base_line_data, to_update = tax_data["base_lines_to_update"][0]

            base_move_line = {
                "name": line_name,
                "account_id": base_line_data["account"].id,
                "product_id": base_line_data["product"].id,
                "analytic_distribution": base_line_data["analytic_distribution"],
                "expense_id": expense.id,
                "tax_ids": [Command.set(expense.tax_ids.ids)],
                "tax_tag_ids": to_update["tax_tag_ids"],
            }

            total_tax_line_balance = 0.0
            for tax_line_data in tax_data["tax_lines_to_add"]:
                tax_line_balance = currency.round(tax_line_data["tax_amount"])
                total_tax_line_balance += tax_line_balance
                tax_line = {
                    "name": f"{entry_ref}: {self.env['account.tax'].browse(tax_line_data['tax_id']).name}",
                    "account_id": tax_line_data["account_id"],
                    "analytic_distribution": tax_line_data["analytic_distribution"],
                    "expense_id": expense.id,
                    "tax_tag_ids": tax_line_data["tax_tag_ids"],
                    "balance": tax_line_balance,
                    "tax_base_amount": currency.round(tax_line_data["base_amount"]),
                    "tax_repartition_line_id": tax_line_data["tax_repartition_line_id"],
                }
                move_lines.append(tax_line)

            base_move_line["balance"] = currency.round(expense.total_amount_company - total_tax_line_balance)
            move_lines.append(base_move_line)

            partner = self._get_employee_fallback_partner()
            move_lines.append(
                {
                    "name": line_name,
                    "account_id": expense._get_expense_account_destination(),
                    "partner_id": partner.id,
                    "expense_id": expense.id,
                    "balance": -currency.round(expense.total_amount_company),
                }
            )

        return {
            **self._prepare_move_vals(),
            "journal_id": entry_journal.id,
            "move_type": "entry",
            "ref": entry_ref,
            "line_ids": [Command.create(line) for line in move_lines],
        }

    def _prepare_bill_vals(self):
        self.ensure_one()
        move_vals = super()._prepare_bill_vals()
        move_vals["ref"] = self._get_invoice_reference()
        if not move_vals.get("partner_id"):
            partner = self._get_employee_fallback_partner()
            move_vals["partner_id"] = partner.id
            move_vals["commercial_partner_id"] = partner.id
        return move_vals

    def _copy_invoice_expense_attachments_to_move(self, move):
        """Copy hr.expense attachments to vendor bill for invoice-type expenses.
        Deduplicate attachments on target move by (checksum, name, mimetype).
        """
        self.ensure_one()
        invoice_expenses = self.expense_line_ids.filtered(lambda exp: exp.expense_document_type == "invoice")
        if not invoice_expenses or move.move_type != "in_invoice":
            return

        source_attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "hr.expense"), ("res_id", "in", invoice_expenses.ids)]
        )
        if not source_attachments:
            return

        existing_attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", move.id)]
        )
        existing_keys = {
            (att.checksum or False, att.name or False, att.mimetype or False)
            for att in existing_attachments
        }
        for attachment in source_attachments:
            key = (attachment.checksum or False, attachment.name or False, attachment.mimetype or False)
            if key in existing_keys:
                continue
            attachment.copy({"res_model": move._name, "res_id": move.id})
            existing_keys.add(key)

    def _do_create_moves(self):
        self = self.with_context(clean_context(self.env.context))
        skip_context = {
            "skip_invoice_sync": True,
            "skip_invoice_line_sync": True,
            "skip_account_move_synchronization": True,
            "check_move_validity": False,
        }

        own_account_sheets = self.filtered(lambda sheet: sheet.payment_mode == "own_account")
        entry_sheets = own_account_sheets.filtered(lambda sheet: sheet._is_entry_sheet())
        invoice_sheets = own_account_sheets - entry_sheets
        company_account_sheets = self - own_account_sheets

        invoice_moves = self.env["account.move"].create([sheet._prepare_bill_vals() for sheet in invoice_sheets])
        for sheet, move in zip(invoice_sheets, invoice_moves):
            sheet._copy_invoice_expense_attachments_to_move(move)

        moves = invoice_moves
        if entry_sheets:
            moves |= self.env["account.move"].create([sheet._prepare_entry_vals() for sheet in entry_sheets])

        payments = self.env["account.payment"].with_context(**skip_context).create(
            [sheet._prepare_payment_vals() for sheet in company_account_sheets]
        )
        payment_moves = payments.move_id
        moves |= payment_moves

        # Keep vendor bills in draft; only post entry/payment moves.
        (moves - invoice_moves).action_post()
        self.activity_update()
        return moves

    def action_sheet_move_create(self):
        samples = self.mapped("expense_line_ids.sample")
        if samples.count(True):
            if samples.count(False):
                raise UserError(_("You can't mix sample expenses and regular ones"))
            self.write({"state": "post"})
            return

        if any(sheet.state != "approve" for sheet in self):
            raise UserError(_("You can only generate accounting entry for approved expense(s)."))

        if any(
            sheet.payment_mode == "own_account" and not sheet._is_entry_sheet() and not sheet.journal_id
            for sheet in self
        ):
            raise UserError(_("Please specify an expense journal in order to generate accounting entries."))

        if any(sheet.payment_mode == "own_account" and sheet._is_entry_sheet() and not sheet._get_entry_journal() for sheet in self):
            raise UserError(_("Please specify an Expense Entry Journal in settings in order to generate accounting entries."))

        if any(not sheet.bank_journal_id for sheet in self if sheet.payment_mode == "company_account"):
            raise UserError(_("Please specify a bank journal in order to generate accounting entries."))

        expense_line_ids = self.mapped("expense_line_ids").filtered(
            lambda r: not float_is_zero(
                r.total_amount,
                precision_rounding=(r.currency_id or self.env.company.currency_id).rounding,
            )
        )
        res = expense_line_ids.with_context(clean_context(self.env.context)).action_move_create()

        paid_expenses_company = self.filtered(lambda m: m.payment_mode == "company_account")
        paid_expenses_company.write({"state": "done", "amount_residual": 0.0, "payment_state": "paid"})

        paid_expenses_employee = self - paid_expenses_company
        paid_expenses_employee.write({"state": "post"})

        self.activity_update()
        return res
