=========================
HR Expense Auto Validate
=========================

Modulo Odoo 16 que automatiza la validacion del parte de gastos.

Funcionamiento
--------------

- Depende de `hr_expense_document_type`.
- Ajuste por compania: `Auto-validate employee expenses`.
- Si esta desactivado, el flujo de `hr_expense` queda igual.
- Si esta activado:

  - al enviar gastos sueltos se crea el parte automaticamente;
  - al enviar el parte se valida la distribucion analitica;
  - el parte se aprueba sin paso manual;
  - se crea el documento contable final (`entry` o factura) segun el tipo.

Uso rapido
----------

1. Configurar `HR Expenses / Settings`.
2. Activar `Auto Validate Expenses`.
3. Enviar el gasto o el parte.
4. Odoo deja el parte contabilizado si todo es valido.
