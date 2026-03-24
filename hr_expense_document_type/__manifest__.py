{
    "name": "HR Expense Document Type",
    "version": "16.0.1.0.0",
    "summary": "Expense lines with Invoice/Entry behavior and optional auto-processing",
    "license": "AGPL-3",
    "author": "zvERP",
    "depends": ["hr_expense", "account"],
    "category": "Human Resources/Expenses",
    "data": [
        "views/hr_expense_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml"
    ],
    "installable": True,
}
