# Security

| Area | What is in place |
|---|---|
| Authentication | Django sessions, hashed passwords with Django validators, login throttled (10/min), password change throttled |
| Authorization | Permission + location checked in the backend on every endpoint (`apps/accounts/api.py`); deny by default (`IsAuthenticated` default, unknown permission = deny); tests for forbidden cases |
| CSRF | Session cookie + `X-CSRFToken` on all unsafe requests (tested: POST without token = 403). In development localhost and 127.0.0.1 dev ports are trusted automatically; in production only origins in `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Secrets | `.env` (never committed); `DJANGO_SECRET_KEY` has no default; `.env.example` is the template |
| SQL injection | Django ORM only, no raw SQL |
| XSS | React escapes output; invoice template uses Django auto-escaping |
| Money/stock integrity | Transactions + row locks, DB check constraints, append-only ledger/payments/audit |
| Audit | Who/what/when/old/new/reason for sensitive actions; audit rows cannot be edited or deleted |
| Deletion rules | Hard delete only when nothing depends on a record (else a clear 400 asks you to deactivate). Invoices, payments, ledger, audit are never deletable. Payroll and expenses are voided with a reason. Attendance edits/deletes need a reason and are audited |
| Salary privacy | Salary fields hidden unless `payroll.manage` (tested) |
| GPS privacy | Consent required, only during a duty session, location-scoped viewing, 30-day purge command |
| Cookies | `Secure` cookies when `DJANGO_DEBUG=False` |

**Before going live** (also in DEPLOYMENT.md): `DJANGO_DEBUG=False`, long random secret key, HTTPS only, change every demo password
(or delete demo users), restrict PostgreSQL to the app host, encrypted off-site backups, set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`, run `python manage.py check --deploy`.

**Known gaps:** no password reset/2FA, no virus scanning on image uploads (only Pillow's image validation), no SMS/OTP login for customers yet.
Common mistakes to avoid: committing `.env`, trusting hidden buttons instead of backend checks, using floats for money, editing stock numbers directly instead of posting movements.
