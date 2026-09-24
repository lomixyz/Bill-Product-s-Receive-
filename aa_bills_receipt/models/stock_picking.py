# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    vendor_bill_id = fields.Many2one(
        'account.move', string="Vendor Bill", copy=False, readonly=True,
        index='btree_not_null', ondelete='set null',
        help="Vendor bill this receipt was created from.")
