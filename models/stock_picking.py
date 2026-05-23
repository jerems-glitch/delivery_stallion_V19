# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    stallion_shipment_id = fields.Char(
        string='Stallion Shipment ID',
        copy=False,
        readonly=True,
    )
    stallion_label_url = fields.Char(
        string='Label URL',
        copy=False,
        readonly=True,
    )
    stallion_postage_code = fields.Char(
        string='Postage Code',
        copy=False,
        readonly=True,
    )

    def action_stallion_get_rates(self):
        """Manually re-fetch rates from the picking view."""
        self.ensure_one()
        if not self.carrier_id or self.carrier_id.delivery_type != 'stallion_express':
            raise UserError(_('Please select a Stallion Express delivery carrier first.'))
        if not self.sale_id:
            raise UserError(_('This picking is not linked to a sale order.'))
        rate = self.carrier_id.stallion_express_rate_shipment(self.sale_id)
        if not rate['success']:
            raise UserError(rate['error_message'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stallion Express Rate'),
                'message': _('Quoted price: %.2f %s') % (
                    rate['price'], self.sale_id.currency_id.name
                ),
                'type': 'success',
            },
        }
