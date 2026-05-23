# -*- coding: utf-8 -*-
import json
import logging
import requests

_logger = logging.getLogger(__name__)

STALLION_PROD_URL = 'https://ship.stallionexpress.ca/api/v4'
STALLION_SANDBOX_URL = 'https://sandbox.stallionexpress.ca/api/v4'


class StallionExpressRequest:
    """Low-level helper that wraps Stallion Express REST API v4."""

    def __init__(self, api_token, prod_environment=True, debug_logger=None):
        self.api_token = api_token
        self.base_url = STALLION_PROD_URL if prod_environment else STALLION_SANDBOX_URL
        self.debug_logger = debug_logger

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_headers(self):
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _request(self, method, endpoint, payload=None):
        url = f'{self.base_url}/{endpoint.lstrip("/")}'
        headers = self._get_headers()

        if self.debug_logger:
            self.debug_logger(
                f'[Stallion] {method.upper()} {url}  payload={json.dumps(payload or {})}',
                'stallion_express',
                'request',
            )

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception('Stallion Express API timed out. Please try again.')
        except requests.exceptions.ConnectionError as e:
            raise Exception(f'Cannot connect to Stallion Express API: {e}')
        except requests.exceptions.HTTPError as e:
            try:
                err_body = response.json()
                msg = err_body.get('message') or err_body.get('error') or str(e)
            except Exception:
                msg = str(e)
            raise Exception(f'Stallion Express API error: {msg}')

        result = response.json()

        if self.debug_logger:
            self.debug_logger(
                f'[Stallion] response={json.dumps(result)}',
                'stallion_express',
                'response',
            )

        return result

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_rates(self, payload):
        """POST /rates — validate and return available shipping rates."""
        return self._request('POST', '/rates', payload)

    def create_shipment(self, payload):
        """POST /shipments — create a shipment and get the postage label."""
        return self._request('POST', '/shipments', payload)

    def get_shipment(self, shipment_id):
        """GET /shipments/{id} — retrieve a single shipment."""
        return self._request('GET', f'/shipments/{shipment_id}')

    def void_shipment(self, shipment_id):
        """DELETE /shipments/{id} — void/cancel a shipment."""
        return self._request('DELETE', f'/shipments/{shipment_id}')

    def track_shipment(self, tracking_code):
        """GET /shipments/track — get tracking events."""
        return self._request('GET', f'/shipments/track?tracking_code={tracking_code}')

    def get_postage_types(self):
        """GET /postage-types — list available postage services."""
        return self._request('GET', '/postage-types')

    def create_order(self, payload):
        """POST /orders — create an order in the Stallion dashboard."""
        return self._request('POST', '/orders', payload)

    def get_locations(self):
        """GET /locations — list Stallion Express drop-off locations."""
        return self._request('GET', '/locations')
