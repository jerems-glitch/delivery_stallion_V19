# delivery_stallion — Stallion Express Shipping for Odoo 17

A complete Odoo delivery carrier module that integrates **Stallion Express API v4**
to display live shipping rates at website checkout and automate label generation.

---

## Features

| Feature | Details |
|---|---|
| Live rates at checkout | Calls `POST /rates` in real-time when customer fills shipping address |
| Multiple service levels | All services returned by the API (Canada Post, USPS, UPS, FedEx via Stallion) |
| Label generation | Creates shipment + downloads PDF/PNG/ZPL label attached to the picking |
| Order sync | Pushes sale orders to Stallion Express dashboard |
| Shipment tracking | Links tracking number; opens Stallion tracking page |
| Shipment voiding | Cancel/void label from within Odoo |
| Sandbox / Production toggle | Switch per carrier config |
| Rate markup | Add fixed $ or % margin on top of Stallion quoted rates |
| Connection test | One-click API connectivity check from the carrier form |

---

## Installation

1. Copy the `delivery_stallion` folder into your Odoo **addons** path.
2. Restart the Odoo server.
3. In Odoo go to **Apps → Update App List**, then search for **"Stallion Express Shipping"** and install.

### Dependencies (Python)
```
requests>=2.28
```
All other dependencies (`delivery`, `sale`, `stock`, `website_sale`) are standard Odoo modules.

---

## Configuration

1. Go to **Inventory → Configuration → Delivery Methods** (or **Website → Configuration → Shipping Methods**).
2. Click **Create** and select **Stallion Express** as the provider.
3. Open the **Stallion Express** tab:
   - Paste your **API Token** (from `stallionexpress.ca → Account Settings → API Token`).
   - Leave **Production Environment** unchecked while testing.
   - Set your preferred **Package Type**, **Weight Unit**, and **Label Format**.
   - Optionally add a **Rate Markup**.
4. Click **Test Connection** — you should see "X postage types available."
5. Set **Pricing** to *"Based on Rules"* or leave it as *"Fixed"* — the module overrides the price with the live Stallion quote at checkout.
6. **Activate** the carrier and publish it on the website.

---

## How it works at checkout

```
Customer enters shipping address
        ↓
Odoo calls stallion_express_rate_shipment()
        ↓
Module POSTs to https://ship.stallionexpress.ca/api/v4/rates
        ↓
Returns cheapest rate (+ markup) → shown to customer
        ↓
Customer confirms order
        ↓
Warehouse validates picking → stallion_express_send_shipping()
        ↓
Module POSTs to /shipments → label downloaded & attached to picking
```

---

## API Endpoints Used

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/rates` | Get live shipping rates |
| POST | `/shipments` | Create shipment & get label |
| GET | `/shipments/{id}` | Get shipment details |
| DELETE | `/shipments/{id}` | Void/cancel shipment |
| GET | `/shipments/track` | Tracking events |
| GET | `/postage-types` | List available services (test connection) |
| POST | `/orders` | Push order to Stallion dashboard |

Base URLs:
- **Production**: `https://ship.stallionexpress.ca/api/v4`
- **Sandbox**: `https://sandbox.stallionexpress.ca/api/v4`

---

## Supported Odoo Versions
- **Odoo 17** (Community & Enterprise)

To backport to Odoo 16: change `'version': '17.0.1.0.0'` in `__manifest__.py`
and adjust any field-level `attrs` to use Odoo 16 syntax.

---

## File Structure

```
delivery_stallion/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── stallion_request.py     ← Low-level API client
│   ├── delivery_carrier.py     ← Carrier methods (rate, ship, track, cancel)
│   └── stock_picking.py        ← Extra fields & manual rate fetch button
├── controllers/
│   ├── __init__.py
│   └── main.py                 ← JSON endpoints for website AJAX
├── views/
│   ├── delivery_carrier_views.xml
│   └── stock_picking_views.xml
├── data/
│   └── delivery_stallion_data.xml
├── security/
│   └── ir.model.access.csv
└── static/src/
    └── css/stallion.css
```

---

## Support

For Stallion Express API issues: **developersupport@stallionexpress.ca**
API docs: **https://stallionexpress.redoc.ly/**
