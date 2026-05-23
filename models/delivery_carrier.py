# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .stallion_request import StallionExpressRequest

_logger = logging.getLogger(__name__)


class ProviderStallion(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('stallion_express', 'Stallion Express')],
        ondelete={'stallion_express': 'set default'},
    )

    # ── Credentials ─────────────────────────────────────────────────────
    stallion_api_token = fields.Char(
        string='API Token',
        help='Bearer token found in Stallion Express: Account Settings → API Token',
    )
    # NOTE: Odoo 18+ has a built-in prod_environment field on delivery.carrier.
    # We keep our own as a fallback in case it is not present.
    stallion_prod_environment = fields.Boolean(
        string='Use Production API',
        default=False,
        help='Uncheck to use the Stallion Express sandbox for testing.',
    )

    # ── Shipping options ─────────────────────────────────────────────────
    stallion_default_package_code = fields.Selection(
        selection=[
            ('package', 'Package / Parcel'),
            ('thick_envelope', 'Thick Envelope'),
            ('flat_rate_box', 'Flat Rate Box'),
        ],
        string='Default Package Type',
        default='package',
    )
    stallion_default_weight_unit = fields.Selection(
        selection=[('lbs', 'lbs'), ('oz', 'oz'), ('kg', 'kg'), ('g', 'g')],
        string='Weight Unit',
        default='lbs',
    )
    stallion_store_id = fields.Char(
        string='Stallion Store ID',
        help='Optional: associate shipments with a specific store in your Stallion account.',
    )
    stallion_markup_type = fields.Selection(
        selection=[('fixed', 'Fixed Amount'), ('percent', 'Percentage')],
        string='Rate Markup Type',
        default='fixed',
    )
    stallion_markup_amount = fields.Float(
        string='Rate Markup',
        default=0.0,
        help='Extra amount (or %) to add on top of the Stallion quoted rate.',
    )
    stallion_signature_required = fields.Boolean(
        string='Require Signature',
        default=False,
    )
    stallion_insurance = fields.Boolean(
        string='Add Shipment Protection',
        default=False,
    )
    stallion_label_format = fields.Selection(
        selection=[('pdf', 'PDF'), ('png', 'PNG'), ('zpl', 'ZPL (thermal)')],
        string='Label Format',
        default='pdf',
    )
    # Store the last quoted service so it is used when creating the shipment
    stallion_last_postage_code = fields.Char(string='Last Postage Code', copy=False)
    stallion_last_carrier_code = fields.Char(string='Last Carrier Code', copy=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _stallion_is_production(self):
        """Return True when the carrier is set to use the live API."""
        # Odoo 18+ exposes prod_environment on the base model; fall back to ours.
        if hasattr(self, 'prod_environment'):
            return bool(self.prod_environment)
        return bool(self.stallion_prod_environment)

    def _stallion_client(self):
        self.ensure_one()
        if not self.stallion_api_token:
            raise UserError(_(
                'Please configure your Stallion Express API Token '
                '(Account Settings → API Token on stallionexpress.ca).'
            ))
        return StallionExpressRequest(
            api_token=self.stallion_api_token,
            prod_environment=self._stallion_is_production(),
        )

    def _stallion_convert_weight(self, weight_kg):
        unit = self.stallion_default_weight_unit
        if unit == 'lbs':
            return round(weight_kg * 2.20462, 4)
        if unit == 'oz':
            return round(weight_kg * 35.274, 4)
        if unit == 'g':
            return round(weight_kg * 1000, 4)
        return round(weight_kg, 4)  # kg

    def _stallion_apply_markup(self, price):
        if self.stallion_markup_type == 'percent':
            return price * (1 + self.stallion_markup_amount / 100)
        return price + self.stallion_markup_amount  # fixed (default)

    @staticmethod
    def _stallion_build_address(partner):
        return {
            'name': partner.name or '',
            'company': partner.commercial_company_name or '',
            'address1': partner.street or '',
            'address2': partner.street2 or '',
            'city': partner.city or '',
            'province_code': partner.state_id.code if partner.state_id else '',
            'postal_code': partner.zip or '',
            'country_code': partner.country_id.code if partner.country_id else '',
            'phone': partner.phone or partner.mobile or '',
            'email': partner.email or '',
            'is_residential': not partner.is_company,
        }

    def _stallion_build_from_address(self):
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1
        )
        partner = (
            warehouse.partner_id
            if warehouse and warehouse.partner_id
            else self.company_id.partner_id
        )
        return self._stallion_build_address(partner)

    def _stallion_rate_payload(self, order):
        total_weight_kg = sum(
            (line.product_id.weight or 0) * line.product_uom_qty
            for line in order.order_line
            if line.product_id and line.product_id.type in ('product', 'consu')
        ) or 0.5

        items = [
            {
                'title': line.product_id.name,
                'sku': line.product_id.default_code or '',
                'quantity': int(line.product_uom_qty),
                'value': line.price_unit,
                'currency': order.currency_id.name,
                'country_of_origin': (
                    line.product_id.country_of_origin.code
                    if line.product_id.country_of_origin else 'CA'
                ),
            }
            for line in order.order_line
            if line.product_id and not line.is_delivery
        ]

        return {
            'to_address': self._stallion_build_address(order.partner_shipping_id),
            'return_address': self._stallion_build_from_address(),
            'weight_unit': self.stallion_default_weight_unit,
            'weight': self._stallion_convert_weight(total_weight_kg),
            'package_code': self.stallion_default_package_code,
            'value': order.amount_untaxed,
            'currency': order.currency_id.name,
            'signature': self.stallion_signature_required,
            'stallion_protection': self.stallion_insurance,
            'items': items,
        }

    # ------------------------------------------------------------------
    # Odoo delivery carrier interface (methods called by Odoo core)
    # ------------------------------------------------------------------

    def stallion_express_rate_shipment(self, order):
        """Return live rate. Called by Odoo at checkout / on sale order."""
        client = self._stallion_client()
        try:
            result = client.get_rates(self._stallion_rate_payload(order))
        except Exception as e:
            return {
                'success': False, 'price': 0.0,
                'error_message': str(e), 'warning_message': False,
            }

        if not result.get('success') or not result.get('data'):
            return {
                'success': False, 'price': 0.0,
                'error_message': result.get('message', 'No rates returned from Stallion Express.'),
                'warning_message': False,
            }

        rates = result['data']
        chosen = min(rates, key=lambda r: r.get('total_rate', float('inf')))
        price = self._stallion_apply_markup(float(chosen.get('total_rate', 0)))

        self.sudo().write({
            'stallion_last_postage_code': chosen.get('postage_code', ''),
            'stallion_last_carrier_code': chosen.get('carrier_code', ''),
        })

        return {
            'success': True,
            'price': price,
            'error_message': False,
            'warning_message': False,
        }

    def stallion_express_send_shipping(self, pickings):
        """Create shipment(s) in Stallion and return tracking info."""
        client = self._stallion_client()
        results = []

        for picking in pickings:
            payload = self._build_shipment_payload(picking)
            try:
                result = client.create_shipment(payload)
            except Exception as e:
                raise UserError(_('Stallion Express shipment creation failed: %s') % str(e))

            if not result.get('success') or not result.get('data'):
                raise UserError(
                    _('Stallion Express error: %s') % result.get('message', 'Unknown error')
                )

            data = result['data']
            tracking = data.get('tracking_code', '')
            label_url = data.get('label_url', '')

            picking.sudo().write({
                'stallion_shipment_id': data.get('id', ''),
                'stallion_label_url': label_url,
                'stallion_postage_code': data.get('postage_code', ''),
            })

            if label_url:
                self._stallion_attach_label(picking, label_url, tracking)

            results.append({
                'exact_price': float(data.get('total_rate', 0)),
                'tracking_number': tracking,
            })

        return results

    def stallion_express_get_tracking_link(self, picking):
        if picking.carrier_tracking_ref:
            return f'https://stallionexpress.ca/tracking/{picking.carrier_tracking_ref}'
        return False

    def stallion_express_cancel_shipment(self, pickings):
        client = self._stallion_client()
        for picking in pickings:
            if picking.stallion_shipment_id:
                try:
                    client.void_shipment(picking.stallion_shipment_id)
                except Exception as e:
                    raise UserError(_('Could not void Stallion shipment: %s') % str(e))
            picking.sudo().write({
                'carrier_tracking_ref': False,
                'carrier_price': 0.0,
                'stallion_shipment_id': False,
                'stallion_label_url': False,
            })

    # ------------------------------------------------------------------
    # Shipment payload builder
    # ------------------------------------------------------------------

    def _build_shipment_payload(self, picking):
        order = picking.sale_id
        currency = order.currency_id.name if order else 'CAD'
        value = order.amount_untaxed if order else 0.0

        total_weight_kg = sum(
            (move.product_id.weight or 0) * move.product_uom_qty
            for move in picking.move_ids
            if move.product_id
        ) or 0.5

        items = [
            {
                'title': move.product_id.name,
                'sku': move.product_id.default_code or '',
                'quantity': int(move.product_uom_qty),
                'value': move.product_id.lst_price,
                'currency': currency,
                'country_of_origin': (
                    move.product_id.country_of_origin.code
                    if move.product_id.country_of_origin else 'CA'
                ),
            }
            for move in picking.move_ids
            if move.product_id
        ]

        payload = {
            'to_address': self._stallion_build_address(picking.partner_id),
            'return_address': self._stallion_build_from_address(),
            'weight_unit': self.stallion_default_weight_unit,
            'weight': self._stallion_convert_weight(total_weight_kg),
            'package_code': self.stallion_default_package_code,
            'label_format': self.stallion_label_format,
            'value': value,
            'currency': currency,
            'signature': self.stallion_signature_required,
            'stallion_protection': self.stallion_insurance,
            'items': items,
        }

        if self.stallion_last_postage_code:
            payload['postage_code'] = self.stallion_last_postage_code
        if self.stallion_last_carrier_code:
            payload['carrier_code'] = self.stallion_last_carrier_code
        if self.stallion_store_id:
            payload['store_id'] = self.stallion_store_id

        return payload

    def _stallion_attach_label(self, picking, label_url, tracking_number):
        try:
            import base64
            import requests as req
            resp = req.get(label_url, timeout=30)
            resp.raise_for_status()
            ext = self.stallion_label_format or 'pdf'
            self.env['ir.attachment'].create({
                'name': f'Stallion_{tracking_number}.{ext}',
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'datas': base64.b64encode(resp.content).decode(),
                'mimetype': f'application/{ext}',
            })
        except Exception as e:
            _logger.warning('Could not download Stallion label: %s', e)

    # ------------------------------------------------------------------
    # Test connection button
    # ------------------------------------------------------------------

    def action_stallion_test_connection(self):
        self.ensure_one()
        client = self._stallion_client()
        try:
            result = client.get_postage_types()
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Connection failed: %s') % str(e))

        if result.get('success'):
            count = len(result.get('data', []))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('%d postage types available from Stallion Express.') % count,
                    'type': 'success',
                },
            }
        raise UserError(_('API responded with failure: %s') % result.get('message', ''))
