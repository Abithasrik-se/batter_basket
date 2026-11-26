# API reference

Base URL: `/api/v1/`. Session-cookie authentication; every non-GET request needs the `X-CSRFToken` header
(the React app does this automatically, see `frontend/src/lib/api.ts`). Lists are paginated
(`?page=2`) and support `?search=`, `?ordering=` and the filters listed in each ViewSet.

**Errors**

| Status | Meaning |
|---|---|
| 400 | Validation error or business rule (`{"detail": "Insufficient stock of Rice ..."}`) |
| 401/403 | Not logged in / not allowed (role or location) |
| 404 | Not found, or outside the locations you may see |
| 429 | Rate limited (login: 10/min, password change: 5/min) |

**Permissions column** (generated from the code): `read` = permission needed for GET, `write` = for POST/PUT/PATCH/DELETE,
extra entries are per-action overrides. `authenticated` = any logged-in user. A user must hold the permission **at the location
of the data** (Super Admin: everywhere).

**Money and quantities** are decimal strings (`"275.00"`, `"40.000"`), never floats.

## Business actions (not plain CRUD)

| Action | Request | Effect |
|---|---|---|
| `POST /production-batches/` | `{location, recipe, quantity_produced}` | Consumes raw materials per recipe, creates bulk stock + batch number |
| `POST /production-batches/{id}/package/` | `{package, units, materials?}` | Bulk stock down, packet stock up |
| `POST /purchases/{id}/receive/` | - | Adds purchased material to the ledger (only once) |
| `POST /orders/` | `{customer, location, delivery_address (required), lines:[{package, quantity}], coupon_code?}` | Prices the order (snapshot), applies discounts and GST, calculates the delivery fee itself |
| `PATCH /orders/{id}/` | `{lines?, delivery_address?, scheduled_date?, delivery_instructions?}` | Pending: re-prices everything. Confirmed: instructions only |
| `POST /delivery/quote/` | `{location, delivery_address, lines?, scheduled_date?}` | Delivery charge preview (distance slab + busy-day surge + free-delivery rule) |
| `GET /recipes/{id}/requirements/` | `?quantity&location` | Raw materials needed for a batch and any shortfall |
| `GET/POST /attendance-check/` | `{action: in\|out}` | Employee self check-in / check-out and last 31 days |
| `GET /payroll/preview/` | `?month=YYYY-MM` | Pay per employee computed from attendance |
| `POST /payroll/generate/` | `{month}` | Creates salary entries once per employee per month |
| `POST /payroll/{id}/void/` | `{reason}` | Voids an entry (never deleted) |
| `POST /orders/{id}/confirm/` | - | Reserves stock FIFO by expiry |
| `POST /orders/{id}/dispatch/` | - | Sale movements + invoice issued |
| `POST /orders/{id}/complete/` | - | Delivered; loyalty points awarded once |
| `POST /orders/{id}/cancel/` | `{reason}` | Releases reservation (not after dispatch) |
| `POST /orders/{id}/return/` | `{reason, restock, items:[{line, quantity}]}` | Credit on invoice, optional restock |
| `POST /payments/record/` | `{invoice, method, amount, tender_amount?, reference?}` | Records cash/UPI/bank, change stored separately |
| `POST /payments/{id}/refund/` | `{amount, reason}` | Separate refund row, never edits the payment |
| `POST /cash-closings/` | `{location, date, counted_cash}` | Compares counted vs expected cash |
| `POST /stock/adjust/` | `{bucket, movement_type, quantity_delta, reason}` | Audited adjustment/wastage/expiry/damage |
| `POST /stock/transfer/` | `{bucket, to_location, quantity}` | Out + in movements in one transaction |
| `POST /delivery/assignments/assign/` | `{order, employee, route_sequence}` | Assign a delivery employee |
| `POST /delivery/assignments/{id}/record/` | `{outcome, failed_reason?}` | Employee's append-only delivery record |
| `POST /delivery/assignments/correct/` | `{record, outcome, reason}` | Admin correction (new row + audit entry) |
| `POST /delivery/duty/` | `{action: start\|end\|ping, ...}` | GPS only with consent and an open session |
| `POST /subscriptions/generate-orders/` | `{date?}` | Same job Celery runs daily (idempotent) |
| `GET /dashboard/` | `?from&to&location` | All owner dashboard numbers |
| `GET /invoices/{id}/print/` | - | Printable HTML bill |

## All endpoints

| URL | Methods | Permissions |
|---|---|---|
| `/api/v1/` | GET | authenticated |
| `/api/v1/attendance-check/` | GET,POST | authenticated |
| `/api/v1/attendance/` | GET,POST | read: employees.view / write: employees.manage |
| `/api/v1/attendance/{id}/` | DELETE,GET,PATCH,PUT | read: employees.view / write: employees.manage |
| `/api/v1/audit-logs/` | GET | read: audit.view / write: - |
| `/api/v1/audit-logs/{id}/` | GET | read: audit.view / write: - |
| `/api/v1/auth/change-password/` | POST | authenticated |
| `/api/v1/auth/csrf/` | GET | authenticated |
| `/api/v1/auth/login/` | POST | authenticated |
| `/api/v1/auth/logout/` | POST | authenticated |
| `/api/v1/auth/me/` | GET,PATCH | authenticated |
| `/api/v1/cash-closings/` | GET,POST | read: payments.view / write: cash.close / expected: payments.view |
| `/api/v1/cash-closings/{id}/` | DELETE,GET,PATCH,PUT | read: payments.view / write: cash.close / expected: payments.view |
| `/api/v1/cash-closings/expected/` | GET | read: payments.view / write: cash.close / expected: payments.view |
| `/api/v1/coupons/` | GET,POST | read: customers.view / write: promotions.manage |
| `/api/v1/coupons/{id}/` | DELETE,GET,PATCH,PUT | read: customers.view / write: promotions.manage |
| `/api/v1/customer-addresses/` | GET,POST | read: customers.view / write: customers.manage |
| `/api/v1/customer-addresses/{id}/` | DELETE,GET,PATCH,PUT | read: customers.view / write: customers.manage |
| `/api/v1/customers/` | GET,POST | read: customers.view / write: customers.manage |
| `/api/v1/customers/{id}/` | DELETE,GET,PATCH,PUT | read: customers.view / write: customers.manage |
| `/api/v1/dashboard/` | GET | authenticated |
| `/api/v1/dashboard/export-sales/` | GET | authenticated |
| `/api/v1/delivery/assignments/` | GET | read: delivery.view / write: - / assign: delivery.assign, record: delivery.record, collect: delivery.record, correct: delivery.correct |
| `/api/v1/delivery/assignments/{id}/` | GET | read: delivery.view / write: - / assign: delivery.assign, record: delivery.record, collect: delivery.record, correct: delivery.correct |
| `/api/v1/delivery/assignments/{id}/collect/` | POST | read: delivery.view / write: - / assign: delivery.assign, record: delivery.record, collect: delivery.record, correct: delivery.correct |
| `/api/v1/delivery/assignments/{id}/record/` | POST | read: delivery.view / write: - / assign: delivery.assign, record: delivery.record, collect: delivery.record, correct: delivery.correct |
| `/api/v1/delivery/assignments/assign/` | POST | read: delivery.view / write: - / assign: delivery.assign, record: delivery.record, collect: delivery.record, correct: delivery.correct |
| `/api/v1/delivery/assignments/correct/` | POST | read: delivery.view / write: - / assign: delivery.assign, record: delivery.record, collect: delivery.record, correct: delivery.correct |
| `/api/v1/delivery/duty/` | POST | authenticated |
| `/api/v1/delivery/fee-slabs/` | GET,POST | read: delivery.view / write: delivery.fees |
| `/api/v1/delivery/fee-slabs/{id}/` | DELETE,GET,PATCH,PUT | read: delivery.view / write: delivery.fees |
| `/api/v1/delivery/quote/` | POST | authenticated |
| `/api/v1/delivery/records/` | GET | read: delivery.assign / write: - |
| `/api/v1/delivery/records/{id}/` | GET | read: delivery.assign / write: - |
| `/api/v1/delivery/surge-rules/` | GET,POST | read: delivery.view / write: delivery.fees |
| `/api/v1/delivery/surge-rules/{id}/` | DELETE,GET,PATCH,PUT | read: delivery.view / write: delivery.fees |
| `/api/v1/delivery/tracking/` | GET | authenticated |
| `/api/v1/employees/` | GET,POST | read: employees.view / write: employees.manage |
| `/api/v1/employees/{id}/` | DELETE,GET,PATCH,PUT | read: employees.view / write: employees.manage |
| `/api/v1/expenses/` | GET,POST | read: expenses.view / write: expenses.create |
| `/api/v1/expenses/{id}/` | DELETE,GET,PATCH,PUT | read: expenses.view / write: expenses.create |
| `/api/v1/expenses/{id}/void/` | POST | read: expenses.view / write: expenses.create |
| `/api/v1/health/` | GET | authenticated |
| `/api/v1/holidays/` | GET,POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/holidays/{id}/` | DELETE,GET,PATCH,PUT | read: orders.view / write: subscriptions.manage |
| `/api/v1/invoices/` | GET | read: billing.view / write: - |
| `/api/v1/invoices/{id}/` | GET | read: billing.view / write: - |
| `/api/v1/invoices/{id}/print/` | GET | read: billing.view / write: - |
| `/api/v1/locations/` | GET,POST | read: locations.view / write: locations.manage |
| `/api/v1/locations/{id}/` | DELETE,GET,PATCH,PUT | read: locations.view / write: locations.manage |
| `/api/v1/loyalty/` | GET | read: customers.view / write: - |
| `/api/v1/loyalty/{id}/` | GET | read: customers.view / write: - |
| `/api/v1/memberships/` | GET,POST | read: employees.view / write: employees.manage |
| `/api/v1/memberships/{id}/` | DELETE,GET,PATCH,PUT | read: employees.view / write: employees.manage |
| `/api/v1/notifications/` | GET | authenticated |
| `/api/v1/notifications/{id}/` | GET | authenticated |
| `/api/v1/notifications/{id}/read/` | POST | authenticated |
| `/api/v1/orders/` | GET,POST | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/orders/{id}/` | DELETE,GET,PATCH,PUT | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/orders/{id}/cancel/` | POST | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/orders/{id}/complete/` | POST | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/orders/{id}/confirm/` | POST | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/orders/{id}/dispatch/` | POST | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/orders/{id}/return/` | POST | read: orders.view / write: orders.create / confirm: orders.confirm, dispatch_order: orders.dispatch, complete: orders.dispatch, cancel: orders.cancel, return_items: orders.return |
| `/api/v1/packages/` | GET,POST | read: catalog.view / write: catalog.manage |
| `/api/v1/packages/{id}/` | DELETE,GET,PATCH,PUT | read: catalog.view / write: catalog.manage |
| `/api/v1/payments/` | GET | read: payments.view / write: - / record: payments.record, refund: payments.refund |
| `/api/v1/payments/{id}/` | GET | read: payments.view / write: - / record: payments.record, refund: payments.refund |
| `/api/v1/payments/{id}/refund/` | POST | read: payments.view / write: - / record: payments.record, refund: payments.refund |
| `/api/v1/payments/record/` | POST | read: payments.view / write: - / record: payments.record, refund: payments.refund |
| `/api/v1/payroll/` | GET,POST | read: payroll.manage / write: payroll.manage / preview: payroll.manage, generate: payroll.manage, void: payroll.manage |
| `/api/v1/payroll/{id}/` | DELETE,GET,PATCH,PUT | read: payroll.manage / write: payroll.manage / preview: payroll.manage, generate: payroll.manage, void: payroll.manage |
| `/api/v1/payroll/{id}/void/` | POST | read: payroll.manage / write: payroll.manage / preview: payroll.manage, generate: payroll.manage, void: payroll.manage |
| `/api/v1/payroll/generate/` | POST | read: payroll.manage / write: payroll.manage / preview: payroll.manage, generate: payroll.manage, void: payroll.manage |
| `/api/v1/payroll/preview/` | GET | read: payroll.manage / write: payroll.manage / preview: payroll.manage, generate: payroll.manage, void: payroll.manage |
| `/api/v1/prices/` | GET,POST | read: catalog.view / write: catalog.manage |
| `/api/v1/prices/{id}/` | DELETE,GET,PATCH,PUT | read: catalog.view / write: catalog.manage |
| `/api/v1/production-batches/` | GET,POST | read: production.view / write: production.create / package: packaging.create |
| `/api/v1/production-batches/{id}/` | DELETE,GET,PATCH,PUT | read: production.view / write: production.create / package: packaging.create |
| `/api/v1/production-batches/{id}/package/` | POST | read: production.view / write: production.create / package: packaging.create |
| `/api/v1/products/` | GET,POST | read: catalog.view / write: catalog.manage |
| `/api/v1/products/{id}/` | DELETE,GET,PATCH,PUT | read: catalog.view / write: catalog.manage |
| `/api/v1/promotions/` | GET,POST | read: customers.view / write: promotions.manage |
| `/api/v1/promotions/{id}/` | DELETE,GET,PATCH,PUT | read: customers.view / write: promotions.manage |
| `/api/v1/public-config/` | GET | authenticated |
| `/api/v1/purchases/` | GET,POST | read: purchasing.view / write: purchasing.create / receive: purchasing.create, pay: purchasing.pay |
| `/api/v1/purchases/{id}/` | DELETE,GET,PATCH,PUT | read: purchasing.view / write: purchasing.create / receive: purchasing.create, pay: purchasing.pay |
| `/api/v1/purchases/{id}/pay/` | POST | read: purchasing.view / write: purchasing.create / receive: purchasing.create, pay: purchasing.pay |
| `/api/v1/purchases/{id}/receive/` | POST | read: purchasing.view / write: purchasing.create / receive: purchasing.create, pay: purchasing.pay |
| `/api/v1/raw-materials/` | GET,POST | read: inventory.view / write: inventory.create |
| `/api/v1/raw-materials/{id}/` | DELETE,GET,PATCH,PUT | read: inventory.view / write: inventory.create |
| `/api/v1/recipes/` | GET,POST | read: production.view / write: catalog.manage / requirements: production.view |
| `/api/v1/recipes/{id}/` | DELETE,GET,PATCH,PUT | read: production.view / write: catalog.manage / requirements: production.view |
| `/api/v1/recipes/{id}/requirements/` | GET | read: production.view / write: catalog.manage / requirements: production.view |
| `/api/v1/roles/` | GET | authenticated |
| `/api/v1/settings/` | GET,PATCH | authenticated |
| `/api/v1/stock-movements/` | GET | read: inventory.view / write: - |
| `/api/v1/stock-movements/{id}/` | GET | read: inventory.view / write: - |
| `/api/v1/stock/` | GET | read: inventory.view / write: - / adjust: inventory.adjust, transfer: inventory.transfer |
| `/api/v1/stock/{id}/` | GET | read: inventory.view / write: - / adjust: inventory.adjust, transfer: inventory.transfer |
| `/api/v1/stock/adjust/` | POST | read: inventory.view / write: - / adjust: inventory.adjust, transfer: inventory.transfer |
| `/api/v1/stock/transfer/` | POST | read: inventory.view / write: - / adjust: inventory.adjust, transfer: inventory.transfer |
| `/api/v1/subscription-runs/` | GET | read: orders.view / write: - |
| `/api/v1/subscription-runs/{id}/` | GET | read: orders.view / write: - |
| `/api/v1/subscriptions/` | GET,POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/{id}/` | DELETE,GET,PATCH,PUT | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/{id}/cancel/` | POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/{id}/pause/` | POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/{id}/renew/` | POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/{id}/resume/` | POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/{id}/skip/` | POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/subscriptions/generate-orders/` | POST | read: orders.view / write: subscriptions.manage |
| `/api/v1/suppliers/` | GET,POST | read: purchasing.view / write: purchasing.create |
| `/api/v1/suppliers/{id}/` | DELETE,GET,PATCH,PUT | read: purchasing.view / write: purchasing.create |
| `/api/v1/units/` | GET,POST | read: catalog.view / write: catalog.manage |
| `/api/v1/units/{id}/` | DELETE,GET,PATCH,PUT | read: catalog.view / write: catalog.manage |
| `/api/v1/users/` | GET,POST | read: employees.view / write: employees.manage |
| `/api/v1/users/{id}/` | DELETE,GET,PATCH,PUT | read: employees.view / write: employees.manage |
