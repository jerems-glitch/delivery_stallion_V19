# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class StallionWebsiteCheckout(WebsiteSale):
    """
    Extends the standard website_sale checkout to inject real-time
    Stallion Express rates into the delivery options presented to shoppers.
    """

    @http.route(
        '/shop/stallion/rates',
        type='json',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def stallion_get_rates(self, **kw):
        """
        AJAX endpoint called by the checkout page to fetch live rates.
        Returns a list of available Stallion services with prices.
        """
        order = request.website.sale_get_order()
        if not order:
            return {'error': 'No active cart found.'}

        carrier_id = kw.get('carrier_id')
        if not carrier_id:
            return {'error': 'carrier_id is required.'}

        carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))
        if not carrier.exists() or carrier.delivery_type != 'stallion_express':
            return {'error': 'Invalid carrier.'}

        try:
            from .stallion_request import StallionExpressRequest  # noqa — just for typing
            client = carrier._stallion_client()
            payload = carrier._stallion_rate_payload(order)
            result = client.get_rates(payload)
        except Exception as e:
            return {'error': str(e)}

        if not result.get('success') or not result.get('data'):
            return {'error': result.get('message', 'No rates returned.')}

        rates = []
        for rate in result['data']:
            price = carrier._stallion_apply_markup(float(rate.get('total_rate', 0)))
            rates.append({
                'carrier_code': rate.get('carrier_code', ''),
                'postage_code': rate.get('postage_code', ''),
                'service_name': rate.get('service_name', rate.get('postage_code', '')),
                'price': price,
                'currency': order.currency_id.name,
                'estimated_days': rate.get('estimated_days', ''),
            })

        rates.sort(key=lambda r: r['price'])
        return {'success': True, 'rates': rates}

    @http.route(
        '/shop/stallion/select_service',
        type='json',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def stallion_select_service(self, carrier_id, postage_code, carrier_code, price, **kw):
        """
        Called when the customer picks a specific Stallion service at checkout.
        Updates the delivery line on the sale order.
        """
        order = request.website.sale_get_order()
        if not order:
            return {'error': 'No active cart.'}

        carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))
        if not carrier.exists():
            return {'error': 'Invalid carrier.'}

        # Store chosen service on carrier (per-session preference)
        carrier.sudo().write({
            '_stallion_last_postage_code': postage_code,
            '_stallion_last_carrier_code': carrier_code,
        })

        # Set delivery price on the order
        order.sudo().set_delivery_line(carrier, float(price))

        return {'success': True, 'price': float(price)}
