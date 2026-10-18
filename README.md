# The Gourmet Groove

A full-stack Django e-commerce application for selling chocolate products. Features include custom user profiles, cart and wishlist, coupons, invoices (PDF), returns, notifications, a chatbot, PayPal (sandbox) payments, and modular apps for vendors, delivery, logistics and stock/location management. Built with Django, Python, HTML, CSS and JavaScript.

## Live demo

Deployed on Render (free plan, first load after idle can take ~30s).

Demo login: `demo` / `demo12345`

The demo database is rebuilt from `store/fixtures/demo_data.json` on every deploy (40 products, brands, categories, coupons, vendors, stores).

## Run locally

```bash
python -m venv venv
venv\Scripts\activate        # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000 and log in with `demo` / `demo12345` (admin: `admin` / `admin12345`).

## Deploy to Render

1. Sign in at https://render.com with GitHub.
2. New → Blueprint → select this repository. `render.yaml` configures everything.
3. Click Apply. Optional environment variables: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `DEMO_ADMIN_PASSWORD`.
