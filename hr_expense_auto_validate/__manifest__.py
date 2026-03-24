{
    "name": "HR Expense Auto Validate",
    "version": "16.0.1.0.0",
    "summary": "Auto-submit, auto-approve and auto-create accounting moves for expenses",
    "license": "AGPL-3",
    "author": "zvERP",
    "depends": ["hr_expense_document_type"],
    "category": "Human Resources/Expenses",
    "data": [
        "views/hr_expense_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml"
    ],
    "installable": True,
}
