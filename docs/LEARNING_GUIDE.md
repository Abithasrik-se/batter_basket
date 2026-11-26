# Learning guide: read the code in this order

Goal: understand it well enough to change it yourself. Each step says what to open, what to notice, and a small task.
Run the app first (see README), click through a full flow, then read.

## 0. Vocabulary
- **Model** = a database table (Python class). **Migration** = the recorded change to the tables (`python manage.py makemigrations`, then `migrate`).
- **Serializer** = converts model ⇄ JSON and validates input. **ViewSet** = the HTTP endpoints for a model.
- **Service** = a plain function holding business rules; views call services. This keeps rules in one place and testable.
- **Transaction** (`@transaction.atomic`) = all-or-nothing database changes. **select_for_update** = lock the row so nobody else changes it meanwhile.
- **Hook / query (React)**: `useQuery` fetches and caches API data; `useTranslation` gives the `t()` function.

## 1. The foundation (30 min)
1. `config/settings.py`: where `.env` is read, the database, DRF defaults (login required by default).
2. `apps/core/models.py`: `BaseModel` (UUID ids), `AppendOnlyModel` (cannot edit/delete), `SystemSettings`, `next_number`.
3. `apps/accounts/rbac.py` then `accounts/api.py`: how a permission becomes an HTTP 403, and how a queryset is limited to your locations.
   **Task:** add a new role `packing_helper` that can only `production.view` and `packaging.create`. Where do you add it? (Answer: `rbac.py`, plus `ROLE_LABELS`, then a migration for the choices.) Write a test in `tests/test_api_permissions.py`.

## 2. Stock (the most important part)
1. `apps/inventory/models.py`: `StockBucket` vs `StockMovement`.
2. `apps/inventory/services.py`: read `post_movement` line by line. Why `select_for_update`? What stops negative stock? (code **and** database constraint)
3. `tests/test_inventory_production.py`: read the tests as a specification.
   **Task:** trace "produce 100 L, package 40 L, transfer 10 packets, sell 5" using the Stock and Stock ledger screens, and check each row.

## 3. Production
`apps/production/services.py`: `required_materials` (recipe scaling and unit conversion), `create_batch`, `package_batch`.
**Task:** change the demo recipe so rice is 42 kg per 100 L. Does an old batch change? (No: consumption rows are stored.)

## 4. Orders and money
1. `apps/orders/services.py`: `create_order` (price snapshot, discounts, GST) then `confirm_order`, `dispatch_order`.
2. `apps/core/money.py`: `line_tax`. Work one example by hand: ₹55 inclusive of 5% GST.
3. `apps/billing/services.py`: `record_payment` (cash 500 for a 250 bill) and `close_cash`.
   **Task:** add a "discount reason" field to orders (model, migration, serializer, test). Which files change?

## 5. Permissions in practice
`tests/test_api_permissions.py::test_location_isolation`: prove to yourself that Sivakasi staff cannot touch another site.

## 6. Frontend
1. `src/theme/theme.css` and `tailwind.config.js`: how one file controls brand colours. **Task:** change the accent colour and watch the app.
2. `src/i18n/` and a locale file: add a new label in both languages and use it. Run `npm run i18n:check`.
3. `src/components/ResourcePage.tsx`: one component renders list + search + pagination + create form + row actions from a config.
4. `src/pages/resources.tsx`: read the `orders` and `stock` configs, then **add a new screen** for an existing API endpoint (e.g. `holidays`): copy a config, add a route in `App.tsx` and a nav item in `AppLayout.tsx`.

## 6b. Features worth studying (round 2)
- `apps/delivery/fees.py` + `tests/test_round2.py::DeliveryFeeTests`: a pure calculation with clear inputs and a stored breakdown.
- `apps/hr/payroll.py`: how attendance becomes money (read `credit_for` and `compute`). **Task:** add overtime (hours above 10 paid at 1.5x) and write the tests first.
- `frontend/src/components/ResourcePage.tsx`: how one config produces a table on desktop, cards on phones, create/edit forms, delete with protection and row actions.
- `frontend/src/components/LocationPicker.tsx`: an imperative library (Leaflet) wrapped in a React component.

## 7. Debugging checklist
| Symptom | Look at |
|---|---|
| 403 in the browser | Does the role have the permission *at that location*? (`/api/v1/auth/me/`) |
| 400 with a message | A business rule (read the message; it names the rule) |
| Empty list although data exists | Location scoping: the user has no membership at that location |
| Blank Tamil text / boxes | Font not loaded; check `index.css` imports |
| `[i18n] missing key` | Add the key to both `en` and `ta` |
| Stock looks wrong | Open **Stock ledger**: the sum of movements always equals the balance |

## 8. Git habit
One feature per commit: `git add -A && git commit -m "feat(orders): add discount reason"`. Run `python manage.py test tests` before each commit.
