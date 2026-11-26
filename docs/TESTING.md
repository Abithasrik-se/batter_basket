# Testing

```powershell
cd backend
python manage.py test tests            # everything
python manage.py test tests.test_orders_billing   # one file
```
Tests use PostgreSQL when `DB_ENGINE=postgres` (recommended: it also runs the concurrency test) and SQLite with `DB_ENGINE=sqlite`.

| File | Proves |
|---|---|
| `test_inventory_production.py` | unit conversion (litre/kg with density), no negative stock, ledger is append-only and balances equal the sum of movements, purchase received once, recipe consumption for 100 L, rollback when raw material is short, bulk→packed without double counting, transfers |
| `test_orders_billing.py` | price/GST snapshot, hotel price and discount, composition scheme, full order lifecycle vs ledger, no overselling, cancel releases stock, FIFO and expired batches, returns, cash change stored separately, UPI reference rule, refund limits, immutable payments, cash closing, invoice sequence, buy-5-get-1, coupon limits, loyalty once |
| `test_api_permissions.py` | login/logout, language preference, 401/403, forbidden roles, **location isolation**, owner sees all, only owner changes settings, role-escalation block, salary hidden, full API order→payment→print flow |
| `test_delivery_subscriptions_dashboard.py` | delivery assign/record/collect, append-only records and audited corrections, riders see only their own, GPS consent, tracking permission, subscription idempotency/holiday/pause/expiry, dashboard numbers from transactions |
| `test_round2.py` | delivery slabs / surge / free-delivery / max distance, mandatory delivery address, quote endpoint, slab overlap rule and CRUD, editing pending orders, delete protection with clear message, draft purchase edit/delete, recipe CRUD + requirements, customer with first address and pin, expense edit audit, premium invoice (words, HSN, UPI QR), amount in words, dev CSRF origins, attendance check-in/out, day-credit rules, monthly and hourly pay, missing check-out flagged, payroll generate/void/regenerate, attendance corrections audited |
| `test_concurrency.py` | two simultaneous confirmations cannot reserve the same last packets (PostgreSQL only) |

Frontend: `npm run i18n:check` and `npm run build` (type-check). **There are no automated UI or end-to-end browser tests yet.**

### Manual checklist per module (before relying on it)
Create → edit → list/search/filter → permission denied for a wrong role → wrong-location denied → Tamil view not broken → mobile width → audit entry visible.
Special: production (stock before/after), orders (stock reserved/consumed), payments (outstanding correct), subscriptions (run twice), delivery (rider sees only own).
