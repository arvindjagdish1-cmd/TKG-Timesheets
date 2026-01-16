# Overview & Goals

# TKG Time & Expense (T&E) Portal

Internal web app to replace the company’s spreadsheet-and-email timesheet/expense workflow with a secure, role-based portal that still exports **Excel/PDF** in the existing formats.

This repo is intentionally set up so you can build quickly in Cursor:
- minimal frontend (server-rendered Django templates)
- strong built-in admin UI (Django admin)
- Microsoft OAuth login (Entra ID / Azure AD) with **required email domain** and optional **tenant restriction**
- exports: XLSX (template-filled) + PDF (LibreOffice headless) + combined PDF packs (sorted by seniority/alphabetical)
- automated reminders (Celery beat)

---

## Goals

### Must-have (v1)
- Employee login via Microsoft OAuth (Entra ID)
- Enter time (half-month) and expenses (monthly) via simple UI
- Upload receipts (enforce “receipt required > $20” policy)
- Submit timesheet/expense report (locks edits; can be returned by admin)
- Office Manager dashboard:
  - submission status (who has/hasn’t submitted)
  - review/approve/return with comments
  - exports (XLSX + PDF packs)
- Export artifacts compatible with current downstream process:
  - per-user XLSX based on existing template
  - per-user PDF
  - combined PDFs (timesheets by seniority; expenses by seniority; expenses alphabetical)
- Audit trail on edits + review actions

### Nice-to-have (v2+)
- Graph-based validation rules configured in admin (instead of code)
- QuickBooks/Payroll integrations
- S3/Azure Blob storage for receipts/exports
- Slack/Teams reminders

---

## Tech stack

- Backend: **Django** (Python)
- DB: **PostgreSQL**
- Async jobs: **Celery + Redis**
- Auth: **Microsoft OAuth (Entra ID) via django-allauth**
- UI: Django templates + Bootstrap (optional HTMX)
- Excel export: **openpyxl**
- PDF conversion: **LibreOffice (headless)**
- PDF merge: **pypdf**
- Audit trail: **django-simple-history**

---

## Repository layout

```

tkg_te/
manage.py
tkg_te/                  # Django project settings
apps/
accounts/              # custom User, EmployeeProfile, groups/roles
periods/               # half-month & monthly periods + due dates
timesheets/            # time entry models + validations
expenses/              # expenses, receipts, mileage
reviews/               # approve/return workflow + comments
exports/               # xlsx/pdf generation + merges + zip bundles
notifications/         # reminder jobs (celery)
audit/                 # optional wrappers
templates/
static/
docker/
compose.yml

````

---

## Roles & permissions

Use Django Groups:
- `employees` — can edit their own drafts; can submit
- `office_manager` — can view all; approve/return; run exports; manage charge codes/categories
- `managing_partner` — read-only review + download exports
- `payroll_partner` — read-only download exports
- `accountants` — read-only download exports

**Rule of thumb**:
- employees can never view other employees’ submissions
- only office_manager can approve/return/unlock

---

## Auth: Microsoft OAuth with required domain (+ optional tenant restriction)

We support Microsoft login and then enforce:
1) **email domain allowlist** (e.g., only `@company.com`)
2) optionally **tenant ID allowlist** (single-tenant hardening)

### Entra ID setup (high level)
In Microsoft Entra admin center:
1. Create an **App Registration**
2. Set it to **single tenant** (recommended) or multi-tenant (only if needed)
3. Add a **Web** redirect URI to the Django allauth callback URL
4. Create a **client secret**
5. Ensure OpenID Connect scopes include `openid`, `profile`, `email`

> NOTE: Allauth callback path is typically:
> `/accounts/microsoft/login/callback/`

Example redirect URI you’ll configure in Entra (dev + prod):
```text
http://localhost:8000/accounts/microsoft/login/callback/
https://te.company.com/accounts/microsoft/login/callback/
````

### Domain restriction (required)

We enforce a required email domain in a custom allauth adapter during social login:

* `ALLOWED_EMAIL_DOMAINS=company.com`
* if user signs in with a Microsoft account whose email is not in the allowed domain(s), login is rejected

### Tenant restriction (recommended)

Optionally enforce tenant ID:

* `ALLOWED_TENANT_IDS=<your-tenant-guid>`
* compare the `tid` claim from the ID token (or fetched account metadata) against allowlist

---

## Local development (Docker recommended)

### Requirements

* Docker + Docker Compose

### Quickstart

1. Copy env template

```bash
cp .env.example .env
```

2. Build and start services

```bash
docker compose up --build
```

3. In a second terminal: run migrations + create admin user

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

4. Seed initial data (groups, charge codes, categories, periods)

```bash
docker compose exec web python manage.py seed_roles
docker compose exec web python manage.py seed_reference_data
docker compose exec web python manage.py create_periods --year 2026 --month 1
```

5. Open the app:

```text
http://localhost:8000
http://localhost:8000/admin
```

---

## Environment variables

Create `.env` from `.env.example` and fill in values.

### `.env.example`

```bash
# Django
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=replace-me
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=tkg_te
POSTGRES_USER=tkg_te
POSTGRES_PASSWORD=tkg_te
DATABASE_URL=postgres://tkg_te:tkg_te@db:5432/tkg_te

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Auth: Microsoft OAuth (Entra ID)
MICROSOFT_CLIENT_ID=replace-me
MICROSOFT_CLIENT_SECRET=replace-me
# Set tenant to your tenant GUID for single-tenant, or "common"/"organizations" if needed
MICROSOFT_TENANT=replace-me

# Hardening: restrict who can log in
ALLOWED_EMAIL_DOMAINS=company.com
# Optional: comma-separated tenant GUIDs
ALLOWED_TENANT_IDS=

# File storage (local dev)
MEDIA_ROOT=/app/media
EXPORT_ROOT=/app/exports
```

---

## Production deployment (recommended approach)

### Recommended

* Run app behind a reverse proxy with HTTPS
* Use Docker images and Compose (or Kubernetes if you have it)
* Use managed Postgres
* Store receipts/exports in object storage (S3/Azure Blob) if possible

### Minimum hardening checklist

* `DJANGO_DEBUG=0`
* strong `DJANGO_SECRET_KEY`
* set `DJANGO_ALLOWED_HOSTS` to your domain
* enable secure cookies + HSTS (Django settings)
* ensure the reverse proxy sets `X-Forwarded-Proto`
* lock down file permissions/volumes
* set up backups (DB + uploaded receipts)

---

## Core domain model (summary)

* `accounts.User` (custom user) + `EmployeeProfile`
* `periods.TimesheetPeriod` (half-month) + `periods.ExpenseMonth` (monthly)
* `timesheets.Timesheet`, `TimesheetLine`, `TimeEntry`, `ChargeCode`
* `expenses.ExpenseReport`, `ExpenseItem`, `ExpenseReceipt`, `MileageEntry`, `ExpenseCategory`
* `reviews.ReviewComment` (submit/return/approve actions + comments)
* `exports.*` (artifact models optional; can store metadata on disk + DB rows)

---

## Validations (v1)

### Timesheet

* weekday daily total must be > 0 (configurable exception rules later)
* if hours entered on a “client line”, must have a charge code + label/description
* hours must be 0 <= hours <= 24
* optional: enforce increments (0.25)

### Expenses

* if amount > 20, require receipt upload OR mark `paper_receipt_delivered=True`
* category may require client field

---

## Exports

### Excel

* Use `openpyxl` to fill the existing XLSX template(s)
* Keep template-driven logic (row/column mapping) in `apps/exports/mapping.py`

### PDF conversion

* Convert exported XLSX to PDF using LibreOffice headless
* Merge PDFs into combined packs using `pypdf`

Services will generate:

* Per employee: `timesheet_<period>_<name>.xlsx` + `.pdf`
* Per employee: `expenses_<month>_<name>.xlsx` + `.pdf`
* Combined: `timesheets_<period>_by_seniority.pdf`
* Combined: `expenses_<month>_by_seniority.pdf`
* Combined: `expenses_<month>_alphabetical.pdf`
* Optional: ZIP bundle with all artifacts

---

## Background jobs (Celery)

### What runs in the background

* reminder emails (2 days before due dates)
* export generation (optional: run on demand synchronously in v1)

### Run workers (dev)

If compose includes separate services:

```bash
docker compose up --build
```

If you need to run manually:

```bash
docker compose exec web celery -A tkg_te worker -l INFO
docker compose exec web celery -A tkg_te beat -l INFO
```

---

## Commands (management)

Expected management commands:

* `seed_roles` — creates Django Groups + permissions defaults
* `seed_reference_data` — loads charge codes, categories, internal lines
* `create_periods --year YYYY --month MM` — creates half-month + monthly periods with due/reminder dates
* `send_reminders` — sends reminder emails (used by Celery beat)
* `generate_exports --year YYYY --month MM [--half FIRST|SECOND]` — generates XLSX/PDF packs

---

## Testing & quality

### Run tests

```bash
docker compose exec web python manage.py test
```

### Formatting (optional)

* black
* ruff
* isort

---

## Implementation notes (Cursor TODO list)

### Phase 1: Auth + roles

* [ ] Create custom `User` model (email as username)
* [ ] Add django-allauth + Microsoft provider
* [ ] Implement domain restriction (`ALLOWED_EMAIL_DOMAINS`)
* [ ] (Optional) tenant restriction (`ALLOWED_TENANT_IDS`)
* [ ] Create Groups and assign permissions

### Phase 2: Periods + auto-create records

* [ ] Period models
* [ ] Command to create periods
* [ ] On period creation or nightly job: ensure each active employee has Timesheet + ExpenseReport objects

### Phase 3: Employee data entry

* [ ] Timesheet grid editor (server-rendered; HTMX optional)
* [ ] Expense entry pages + receipt upload + mileage
* [ ] Validate and submit (locks editing)

### Phase 4: Review + exports

* [ ] Office Manager dashboard: submission status
* [ ] Approve/return with comments
* [ ] Export XLSX using template mapping
* [ ] Convert to PDF; merge packs; zip bundle

### Phase 5: Reminders + audit

* [ ] Celery beat reminder schedule
* [ ] Add simple-history or custom audit trail to core models

---

## Security notes

* This system stores financial receipts: treat it as sensitive.
* Enforce least privilege via Django permissions and per-object checks.
* Prefer single-tenant Microsoft app registration.
* Enforce allowed email domains at login (hard block).
* Consider encrypting at-rest storage for receipts/exports if required by policy.
* Add logging for:

  * logins
  * submission events
  * approval/returns
  * export downloads (who, when)

---

## License

Internal company project (private). Add a license only if you plan to open source any part.

```

