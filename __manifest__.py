# -*- coding: utf-8 -*-
{
    'name': 'Stallion Express Shipping',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Stallion Express shipping integration — live rates at checkout',
    'description': """
Stallion Express Shipping Integration for Odoo 19
==================================================
Integrates Stallion Express API v4 with Odoo delivery:
- Live shipping rate quotes at website checkout
- Multiple service levels (Canada Post, USPS, UPS, FedEx via Stallion)
- Automatic label generation on picking validation
- Shipment tracking links
- Sandbox / Production environment toggle
    """,
    'author': 'Custom Development',
    'depends': [
        'delivery',
        'sale',
        'stock',
        'website_sale',
    ],
    'data': [
        'views/delivery_carrier_views.xml',
        'views/stock_picking_views.xml',
        'data/delivery_stallion_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'delivery_stallion/static/src/css/stallion.css',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
