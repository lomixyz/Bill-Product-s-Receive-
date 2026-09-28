# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    receipt_ids = fields.One2many(
        'stock.picking', 'vendor_bill_id', string="Receipts", copy=False, readonly=True)
    receipt_count = fields.Integer(string="Receipts", compute="_compute_receipt_count")
    # Kept for backward compatibility: the last receipt created from this bill.
    picking_id = fields.Many2one('stock.picking', string="Receipt", copy=False)

    def _default_invoice_date(self):
        # Pre-fill the date on purchase documents only. Customer invoices and journal
        # entries keep the standard Odoo behaviour (date set when the document is posted).
        if self.env.context.get('default_move_type') in ('in_invoice', 'in_refund', 'in_receipt'):
            return fields.Date.context_today(self)
        return False

    invoice_date = fields.Date(default=_default_invoice_date)

    @api.depends('receipt_ids.state')
    def _compute_receipt_count(self):
        for move in self:
            # sudo: the counter must not break the form for users without inventory access rights
            receipts = move.sudo().receipt_ids
            move.receipt_count = len(receipts.filtered(lambda p: p.state != 'cancel'))

    # ------------------------------------------------------------------
    # Receipt creation
    # ------------------------------------------------------------------
    def _get_receipt_picking_type(self):
        """Incoming operation type of the bill's company (never one of another company)."""
        self.ensure_one()
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not picking_type:
            raise UserError(_(
                'No receipt operation type found for company %s.', self.company_id.display_name))
        return picking_type

    def _get_receipt_locations(self, picking_type):
        self.ensure_one()
        Location = self.env['stock.location']
        company_domain = [('company_id', 'in', [False, self.company_id.id])]
        source_location = picking_type.default_location_src_id or Location.search(
            [('usage', '=', 'supplier')] + company_domain, limit=1)
        dest_location = picking_type.default_location_dest_id or Location.search(
            [('usage', '=', 'internal')] + company_domain, limit=1)
        if not source_location or not dest_location:
            raise UserError(_('Valid locations not found.'))
        return source_location, dest_location

    def _prepare_receipt_move_vals(self, line, source_location, dest_location):
        """Stock move values for a bill line.

        The unit price is the bill price (company currency, product UoM) so the receipt is
        valued at the billed cost. Odoo 20 values the receipt on its own, straight from the
        stock move, through the locations' valuation accounts (Inventory > Configuration >
        Locations): there is no "stock input account" to redirect the bill line to any more
        (that mechanism from earlier Odoo versions was removed), so this module does not touch
        the bill line's account_id at all.
        """
        self.ensure_one()
        product = line.product_id
        uom = line.product_uom_id or product.uom_id
        price_unit = line.balance / line.quantity if line.quantity else 0.0
        price_unit = uom._compute_price(price_unit, product.uom_id)
        return {
            # Odoo 20 renamed stock.move's free-text label from `name` to `description_picking`
            # (computed/inverse; setting it here stores it as the manual description), and its
            # unit-of-measure field from `product_uom` to `uom_id`.
            'description_picking': line.name or product.display_name,
            'product_id': product.id,
            'product_uom_qty': line.quantity,
            'uom_id': uom.id,
            'price_unit': max(price_unit, 0.0),
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'company_id': self.company_id.id,
            'origin': self.name,
        }

    def _create_receipt(self):
        """Create and confirm the receipt of a posted vendor bill."""
        self.ensure_one()
        picking_type = self._get_receipt_picking_type()
        source_location, dest_location = self._get_receipt_locations(picking_type)

        move_vals_list = [
            self._prepare_receipt_move_vals(line, source_location, dest_location)
            for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
            # Odoo 20 dropped the 'product' (storable) value from product.type: a physical good
            # is always 'consu', with the separate `is_storable` flag telling storable apart from
            # non-storable. Either way it can be received, so only services/combos are excluded.
            if line.product_id and line.product_id.type == 'consu' and line.quantity > 0
        ]
        if not move_vals_list:
            raise UserError(_(
                'Bill %s has no storable or consumable product line to receive.', self.name))

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'move_type': 'direct',
            'vendor_bill_id': self.id,
            'move_ids': [Command.create(vals) for vals in move_vals_list],
        })

        picking.action_confirm()
        picking.action_assign()

        self.picking_id = picking  # last receipt created from this bill
        self.message_post(body=Markup(_("Receipt created: %s")) % picking._get_html_link())
        return picking

    def action_create_receipt(self):
        for bill in self:
            if bill.move_type != 'in_invoice':
                raise UserError(_('This action can only be performed on Vendor Bills.'))
            if bill.state != 'posted':
                raise UserError(_('The bill must be posted before creating a receipt.'))
            if bill.sudo().receipt_ids.filtered(lambda p: p.state != 'cancel'):
                raise UserError(_(
                    'A receipt already exists for bill %s. Cancel it first if you need to create a new one.',
                    bill.name))
            bill._create_receipt()

    def action_view_receipt_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        receipts = self.receipt_ids
        action['domain'] = [('id', 'in', receipts.ids)]
        if len(receipts) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = receipts.id
        return action
