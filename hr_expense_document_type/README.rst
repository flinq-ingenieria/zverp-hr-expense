========================
HR Expense Document Type
========================

Modulo Odoo 16 para distinguir entre gasto contable y gasto con factura. (flujo F)

Que anade
---------

- Campo `Tipo de documento`: `Gasto` / `Factura`.
- Datos de factura: proveedor, numero, fecha y observaciones.
- Ajustes:

  - tipo de documento por defecto;
  - diario miscelaneo para gastos de tipo `Gasto`.

Flujo
-----

- `Gasto` + pago de empleado:

  - agrupa en un parte homogeneo;
  - crea un asiento `entry` en el diario configurado;
  - usa la cuenta acreedora del empleado/partner asociado.

- `Factura`:

  - crea factura de proveedor en borrador;
  - mueve proveedor, numero y fecha a `account.move`;
  - copia adjuntos desde `hr.expense` sin duplicarlos;
  - agrupa por proveedor y numero de factura cuando aplica.

Notas
-----

- No mezcla tipos distintos en el mismo parte para gastos de empleado.
- Si falta el diario de `Gasto`, no deja contabilizar.
