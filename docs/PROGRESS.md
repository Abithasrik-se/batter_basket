# Progress checklist (honest status)

Legend: ✅ built and covered by automated tests · 🟡 built, light or no tests · ⬜ not built

## Foundation
- ✅ Custom user, roles per location (RBAC), permission checks in the backend, location scoping of every queryset
- ✅ Login / logout / me / change password, rate-limited login, CSRF-protected session auth
- ⬜ Password **reset by email** and **account activation** (use the Django admin or `change-password` for now)
- ✅ Edit / delete (or deactivate / void) on every module where it is safe; records that other data depends on cannot be hard-deleted and say so
- ✅ Hints on every page and field, English + Tamil; toast and confirm dialogs; mobile card layout, bottom tab bar, bottom-sheet forms
- ✅ Audit log (login, creates/updates, stock adjustments, payments, refunds, corrections, settings)
- ✅ System settings (business, GST scheme, invoice prefix, language default, theme colours)

## Modules
| Module | Status | Notes |
|---|---|---|
| A Dashboard | ✅ | Calculated from invoices/ledger/batches; CSV sales export. Profit is an *estimate* |
| B Locations | ✅ | Deactivate, never delete |
| C Products, packages, prices | ✅ | Per price group, effective dates, history preserved on orders; product image field exists, no upload screen yet |
| D Raw materials, purchases, suppliers | ✅ | Receive-once rule, supplier payments |
| E Production + recipes | ✅ | Recipe consumption, batch numbers, expiry, quality flag. Recipe creation is API/admin only (demo recipe seeded) |
| F Packaging, stock, transfers | ✅ | Append-only ledger, reservations, FIFO by expiry, adjustments |
| G Supplier/purchase management | ✅ | |
| H Customers | ✅ | Households and hotels, multiple addresses, per-customer discount |
| I Orders | ✅ | create (delivery address mandatory), edit pending orders (items re-priced), confirm, dispatch, complete, cancel, return. Delivery fee is calculated automatically |
| J Billing and payments | ✅ | Cash with change, UPI, bank, credit sales, partial pay, refunds, cash closing, printable bill. **Razorpay/gateway not built** (method name reserved) |
| K Subscriptions | ✅ | Idempotent daily generation, holidays, pause/resume/cancel/renew. Orders are created as *pending* (not auto-confirmed) |
| L Delivery + GPS + charges | ✅ | Distance slabs, busy-day surcharge, free-delivery threshold, max distance, all editable (CRUD). Map pin for addresses (OpenStreetMap). | Assignment, append-only records, corrections, cash collection, consent-based duty session, 30-day purge command. PWA tracking works only while the app is open |
| M Employees, attendance, payroll | ✅ | Daily self check-in/out, admin corrections with reason + audit, payroll computed from attendance (full/half day rules, hourly or monthly), advances/bonus/deductions, void instead of delete |
| N Expenses and finance | 🟡 | Expenses with void, dashboard finance summary. No cash-flow report |
| O Loyalty and offers | 🟡 | Buy-X-get-Y, coupons, points earned once per order. **Points redemption not built** |
| P Notifications | 🟡 | Consent-aware hub, email, in-app stock/expiry alerts. **SMS / WhatsApp / push are stubs** |
| Q Audit + settings | ✅ | |

## Not done / next
1. Password reset and activation by email (staff cannot reset their own password yet)
2. Razorpay (or other) payment gateway + webhook
3. Customer self-service website and "my orders" API (the `customer` role exists but has no screens)
4. SMS/WhatsApp provider integration (needs DLT registration for SMS)
5. Returns/refund screens (API exists)
5b. Production batch quantity edits are intentionally blocked (use stock adjustment); invoices, payments and the stock ledger are intentionally never editable or deletable
6. Frontend component tests and end-to-end browser tests (backend business logic is well covered, UI is not)
7. Docker files and CI are provided but **were not run** in the environment that built this project
8. Offline queue for delivery records on poor networks

## Technical debt to know about
- Stock quantities use 3 decimals; very large volumes need `max_digits` review.
- `OrderReturn.credit_value` is written with a queryset update because the row type is append-only.
- Delivery fee is not taxed (simplification, confirm with your CA).
- Delivery distance is straight-line x a road factor (default 1.3), not real road routing. Map search uses the free OpenStreetMap/Nominatim service (fine for light use; use a paid provider for heavy use).
- The map needs internet; the rest of the PWA shell is cached but data pages need the network.
- UI is verified by type-check, build and a live API check through the dev proxy, not by browser automation.
- The generic `ResourcePage` keeps the UI small but is not ideal for complex screens; move to dedicated pages as needs grow.
