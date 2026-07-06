=======================
HR Expense Vendor Bill
=======================

Modulo Odoo 16 con flujo de factura de proveedor para gastos con factura.

Que anade
---------

- Campo `Tipo de documento`: `Gasto` / `Factura`.
- Datos de factura: proveedor, numero, fecha y observaciones.
- Ajuste: diario miscelaneo para lineas de tipo `Gasto`.

Flujo
-----

- `Factura`:

  - exige proveedor y numero antes de enviar;
  - crea factura de proveedor en borrador;
  - copia adjuntos del gasto a la factura sin duplicados;
  - pasa las observaciones a la narracion.

- `Gasto`:

  - crea un asiento `entry` en diario miscelaneo.

- Aprobacion:

  - conserva el flujo estandar de envio/aprobacion;
  - no auto-aprueba por si mismo.

Notas
-----

- Agrupa gastos de factura por modo de pago, proveedor y numero.
- Las facturas de proveedor se quedan en borrador; los asientos/pagos si se publican.
