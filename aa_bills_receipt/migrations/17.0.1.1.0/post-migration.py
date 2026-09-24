# -*- coding: utf-8 -*-
"""Link the receipts created by former versions to their vendor bill.

Older versions found the receipts of a bill through their `origin` (= bill number), which is
ambiguous in multi-company databases. Receipts are now linked with `stock.picking.vendor_bill_id`.
"""


def migrate(cr, version):
    if not version:
        return
    # 1) Receipts explicitly stored on the bill.
    cr.execute("""
        UPDATE stock_picking sp
           SET vendor_bill_id = am.id
          FROM account_move am
         WHERE am.picking_id = sp.id
           AND sp.vendor_bill_id IS NULL
    """)
    # 2) Other receipts created by the module: origin = bill number, same company.
    cr.execute("""
        UPDATE stock_picking sp
           SET vendor_bill_id = bill.id
          FROM (
                SELECT MIN(id) AS id, name, company_id
                  FROM account_move
                 WHERE move_type = 'in_invoice' AND state = 'posted' AND name IS NOT NULL
              GROUP BY name, company_id
                HAVING COUNT(*) = 1
               ) bill
         WHERE sp.vendor_bill_id IS NULL
           AND sp.origin = bill.name
           AND sp.company_id = bill.company_id
    """)
