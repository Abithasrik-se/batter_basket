# Zeal Enterprises Business Management System

Idli and dosa batter: production, stock, orders, billing, delivery, subscriptions and reports for one or more locations.

**Stack:** Django 5.2 LTS + Django REST Framework, PostgreSQL, Celery/Redis, React 18 + TypeScript + Vite + Tailwind (installable PWA), English and Tamil.

```
backend/    Django API (apps/ = one folder per business module)
frontend/   React PWA (src/pages/resources.tsx defines most screens)
docs/       Guide: architecture, database, API, security, testing, deployment, GST, learning notes
deploy/     nginx + backup script for the Docker deployment
```

## Run it on Windows (PowerShell)

Prerequisites: Python 3.13 or 3.14, Node 20+, PostgreSQL, Git.

```powershell
# 1. Database (once). Replace the password.
psql -U postgres -c "CREATE USER zeal_user WITH PASSWORD 'choose-a-password';"
psql -U postgres -c "CREATE DATABASE zeal_dev OWNER zeal_user;"

# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit .env: DJANGO_SECRET_KEY and DB_PASSWORD
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"   # paste into .env
python manage.py migrate
python manage.py seed_initial --demo      # units, Sivakasi unit, demo products/prices/recipe/users
python manage.py runserver

# 3. Frontend (second window)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Demo login: `owner` / `ChangeMe-12345` (change it immediately). Other demo users (same password): `prod_mgr`, `cashier`, `dispatch`, `rider1`.
`seed_initial` without `--demo` only creates units, settings and the Sivakasi location.

Background jobs (subscriptions, alerts), only needed when you use them:
```powershell
celery -A config worker -l info --pool=solo
celery -A config beat -l info
```
Without Celery, run the same code manually: `POST /api/v1/subscriptions/generate-orders/` or `python manage.py check_alerts`.

## Tests

```powershell
cd backend
python manage.py test tests          # 84 tests, runs on PostgreSQL (or DB_ENGINE=sqlite for a quick run)
cd ../frontend
npm run i18n:check                   # English/Tamil keys in sync, all used keys defined
npm run build                        # type-check + production build
```

## Troubleshooting
| Problem | Fix |
|---|---|
| `CSRF Failed: Origin checking failed` | In development set `DJANGO_DEBUG=True` in `backend/.env` (localhost and 127.0.0.1 on ports 5173/4173/3000/8000 are trusted automatically). In production set `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain` |
| `no such table` / missing columns after updating | `python manage.py migrate` |
| Map does not load | It needs internet access to OpenStreetMap |
| Nothing visible in the menu | The user has no role at a location: Users, then Access & roles |

## First steps after install
1. Settings: business name/address, **GSTIN, GST scheme and product GST rate (confirm with your CA)**, invoice prefix.
2. Products, Packages and Prices: check the demo data, replace with your real sizes and prices.
3. Locations: pin your unit on the map. Delivery, then Delivery charges: set your distance slabs and busy-day rule.
4. Raw materials, a Recipe, a Purchase (then *Receive*), then Production, then Package, then Orders (every order needs a delivery address).
5. Users, Access & roles, Employees: staff then check in/out from the top bar every day and Payroll uses it.

Every page has a *How this page works* panel and a hint under each field. All text is English and Tamil.

Read `docs/PROGRESS.md` for what is complete and what is still to build, and `docs/LEARNING_GUIDE.md` to understand the code.
