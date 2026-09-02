# Onboard Chaser AI — MVP

A secure employee-onboarding document collection system. Candidates receive a
magic-link to a private portal, see the list of required documents with upload
instructions, and submit files directly (PDF / JPG / PNG / GIF) without sending
sensitive information over email. HR tracks completion status and, later,
receives automated reminders.

> Built as an MVP: minimal, maintainable, no over-engineering. AI document
> verification (US12) is explicitly out of scope for the MVP.

---

## 1. Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  React + Vite   │ HTTP │  FastAPI (port   │ SQL  │  PostgreSQL 16   │
│  + Tailwind     │─────▶│  8000)           │─────▶│  (port 5432)     │
│  (port 5173)    │      │  SQLAlchemy ORM  │      └──────────────────┘
└─────────────────┘      │  JWT / magic     │
                         │  links           │      ┌──────────────────┐
                         │                  │ S3   │  Cloudflare R2   │
                         │                  │─────▶│  (S3-compatible) │
                         └──────────────────┘      └──────────────────┘
                                     │  Redis (Celery broker, reserved for US08)
                                     ▼
                          ┌──────────────────┐
                          │  Resend API      │  (email, reserved for US07)
                          └──────────────────┘
```

| Component      | Technology                                   | Port  |
|----------------|----------------------------------------------|-------|
| Frontend       | React 18, Vite 5, Tailwind CSS 3, react-router, lucide-react | 5173  |
| Backend API    | FastAPI 0.111, SQLAlchemy 2.0, Pydantic 2   | 8000  |
| Database       | PostgreSQL 16 (Docker image `postgres:16-alpine`) | 5432  |
| Cache / Broker | Redis 7 (Docker image `redis:7-alpine`)      | 6379  |
| File storage   | Cloudflare R2 via boto3 (S3-compatible), local-filesystem fallback | —     |
| Email          | Resend (`resend` SDK) — wired for US07       | —     |
| Scheduler      | Celery 5 + Redis — wired for US08            | —     |
| Deployment     | Docker + Docker Compose                      | —     |

---

## 2. Project Structure

```
MVP_Project/
├── docker-compose.yml            # Full stack: db, redis, backend, frontend
├── .gitignore
├── .dockerignore               # excludes .env, node_modules, __pycache__, uploads/
├── backend/
│   ├── Dockerfile              # python:3.11-slim-bookworm
│   ├── requirements.txt
│   ├── .env.example            # Copy to .env and fill in secrets
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, router registration
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic-settings (reads .env)
│   │   │   ├── database.py     # SQLAlchemy engine/session
│   │   │   └── security.py     # JWT + magic-link tokens, bcrypt
│   │   ├── models/models.py    # SQLAlchemy ORM: User, Candidate, Onboarding, Document (with file metadata + statuses)
│   │   ├── schemas/schemas.py  # Pydantic models: UserCreate, UserLogin, Token, OnboardingPortalResponse, DocumentResponse, etc.
│   │   ├── api/
│   │   │   ├── auth.py         # POST /auth/register, POST /auth/login
│   │   │   ├── candidates.py   # POST /candidates/
│   │   │   └── onboarding.py   # onboarding, magic-link, portal, document, status, progress, storage endpoints
│   │   └── services/
│   │       ├── onboarding_service.py   # create onboarding, magic links, portal session, completion %, status transitions
│   │       ├── document_service.py     # file validation, encrypted storage upload, metadata linkage
│   │       └── storage.py              # R2/S3 upload, AES-256-Fernet encryption, private bucket, local fallback
│   └── tests/
│       ├── conftest.py           # shared in-memory SQLite test DB + fixtures
│       ├── test_us01.py          # 12 tests — secure portal + magic links
│       ├── test_us02.py          # 11 tests — document checklist
│       ├── test_us03.py          # 18 tests — document upload + validation
│       ├── test_us04.py          # 12 tests — secure storage (R2, encryption, structure, DB linkage)
│       └── test_us05.py          # 14 tests — status tracking + completion percentage
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js            # dev server + /api proxy → VITE_API_URL || localhost:8000
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx              # React entry, BrowserRouter
        ├── App.jsx               # Routes: /, /onboard/:token, /admin/onboarding/new, /admin/settings/reminders
        ├── index.css             # Tailwind + gradient helper
        └── pages/
            ├── HomePage.jsx              # Landing page
            └── OnboardingPortal.jsx    # Checklist + upload UI + progress card (server-driven %)
```

---

## 3. How to Run

### Option A — Docker Compose (recommended, full stack)

Prerequisites: **Docker** with Docker Compose v2.

```bash
# 1. Go to project root
cd "E:\Onboard Chaser AI\MVP_Project"

# 2. Create backend .env from the example
cp backend/.env.example backend/.env
#    (edit backend/.env if you have real credentials — see section 5)

# 3. Build & start all services (db, redis, backend, frontend, celery-worker, celery-beat)
docker compose up --build

# 4. Verify
#    Backend health:  http://localhost:8000/health   → {"status":"healthy"}
#    API docs:        http://localhost:8000/docs     (Swagger UI)
#    Frontend:        http://localhost:5173
#    DB:              postgres://postgres:postgres@localhost:5432/onboard_chaser
#    (host port is 5433 to avoid conflicts with other local Postgres — see section 1 / compose)
#    Reminder scan:   docker compose logs celery-worker   (hourly beat tick)
```

Stop with `Ctrl+C`, then `docker compose down`. To wipe the database volume:
`docker compose down -v`.

> Note: the backend container mounts `./backend` as a volume and uvicorn runs
> with `--reload`, so backend code changes hot-reload inside the container.
> The frontend mounts `./frontend` with a `node_modules` volume, so Vite
> hot-reloads too.

### Option B — Run locally without Docker

Prerequisites: Python 3.11+, Node.js 20+, and a PostgreSQL instance (or a
running `db` container only).

```bash
# --- Backend ---
cd backend
python -m venv .venv
# Windows (git-bash):  source .venv/Scripts/activate
# Linux/macOS:        source .venv/bin/activate
pip install -r requirements.txt

# Point DATABASE_URL at your local Postgres, e.g.:
#   export DATABASE_URL="postgresql://postgres:***@localhost:5432/onboard_chaser"
# (or put it in backend/.env — replace placeholder "your_*" values with real ones)
# If using the bundled compose db, the host port is 5433 (not 5432):
#   export DATABASE_URL="postgresql://postgres:***@localhost:5433/onboard_chaser"

uvicorn app.main:app --reload --port 8000
# API: http://localhost:8000  |  Docs: http://localhost:8000/docs

# --- Frontend (second terminal) ---
cd frontend
npm install
npm run dev
# App: http://localhost:5173
# Vite proxies /api → http://localhost:8000 (default for local dev).
# For Docker, set VITE_API_URL=http://backend:8000 (handled by docker-compose.yml).
```

### Run the tests

```bash
cd backend
TESTING=1 python -m pytest tests/ -v
# Expected: 139 passed (US01: 12, US02: 11, US03: 18, US04: 12, US05: 14, US06: 17, US07: 6, US08: 31, US09: 17)
```

Tests use an in-memory SQLite database (StaticPool) via `tests/conftest.py`, so
they run with **no Docker / no PostgreSQL required**.

---

## 4. What Has Been Implemented (per User Story)

All user stories are tracked in **Plane** (workspace `techco`, project
"On Board Chaser AI") and on **GitHub** (`mryusefi/Onboard-Chaser-AI`), one
feature branch per story.

| Story | Title | Status | Feature branch | Tests |
|-------|-------|--------|----------------|-------|
| US01  | Access onboarding portal via secure link | ✅ Done (merged to main) | `feature/secure-onboarding-portal` | 12 |
| US02  | See the list of required documents | ✅ Done (merged to main) | `feature/document-checklist` | 11 |
| US03  | Upload documents online | ✅ Done (merged to main) | `feature/document-upload` | 18 |
| US04  | Secure document storage (R2) | ✅ Done (merged to main) | `feature/secure-document-storage` | 12 |
| US05  | Document status tracking | ✅ Done (merged to main) | `feature/document-status` | 14 |
| US06  | HR creates a new onboarding process | ✅ Done (feature branch, pending merge) | `feature/hr-onboarding-management` | 17 |
| US07  | Invitation email via Resend | ✅ Done (feature branch, pending merge) | `feature/invitation-email` | 6 |
| US08  | Automated reminder system | ✅ Done (feature branch, pending merge) | `feature/automated-reminders` | 31 |
| US09  | Reminder configuration (admin UI on global `ReminderConfig`) | ✅ Done (feature branch, pending merge) | `feature/reminder-config` (stacked on US08 branch) | 17 |
| US10–11 | HR dashboard + document detail | ⏳ Backlog | — | — |
| US12  | AI document verification | 🚫 Post-MVP (explicitly out of scope) | — | — |

### US01 — Secure Onboarding Portal
- `POST /api/v1/onboarding/{candidate_id}` — create an onboarding process and
  seed the 4 default required documents.
- `POST /api/v1/onboarding/magic-link` — generate a time-limited JWT magic link
  (`FRONTEND_URL/onboard/<token>`), stored on the onboarding record with an
  expiration timestamp.
- `GET /api/v1/onboarding/portal/{token}` — validates the token (signature,
  `type=magic` claim, expiry), marks the token used, starts the session
  (`status → in_progress`), and returns candidate info + document list.
- HR auth scaffold: `POST /auth/register`, `POST /auth/login` (bcrypt + JWT).
- Frontend route `/onboard/:token` with loading / access-denied states.

### US02 — Document Checklist
- `Document` model extended with `instructions` and `accepted_formats`.
- 4 default documents with rich, per-document upload instructions
  (Government ID, Proof of Address, Tax Form W-4 — PDF only —, Signed Offer Letter).
- Portal API returns `instructions`, `accepted_formats`, `required`, `status`
  per document.
- Frontend: numbered step badges, color-coded status chips
  (pending/uploaded/completed/missing), expandable instruction panels with
  format badges, progress bar with percentage.

### US03 — Document Upload
- `app/services/document_service.py`:
  - `validate_file()` — size limit (10 MB), non-empty, extension allow-list
    (`.pdf/.jpg/.jpeg/.png/.gif`), MIME/extension consistency.
  - `upload_file_to_storage()` — uploads to **Cloudflare R2** via boto3
    (S3-compatible) when credentials are configured, otherwise falls back to a
    local `backend/uploads/` directory. Stores metadata: `file_key`
    (random hex + ext), `file_name`, `uploaded_at`, `status → uploaded`.
- `POST /api/v1/onboarding/document/{document_id}/upload` (multipart) —
  validates then persists the file.
- `GET /api/v1/onboarding/document/{document_id}` — fetch upload context.
- Frontend: inline file picker per document card, upload spinner,
  success/error messages, instant status + progress update after upload.

### US04 — Secure Document Storage
- `app/services/storage.py` (new):
  - `storage_path_for()` — structured key `onboardings/{onboarding_id}/{document_id}.{ext}`
  - `encrypt_bytes()` / `decrypt_bytes()` — AES-256-Fernet encryption at rest,
    key derived from `SECRET_KEY` via HKDF-SHA256.
  - `is_r2_configured()` — true only when all R2 credentials are present.
  - `upload_to_r2()` — uploads as a **PRIVATE** object (ACL=private); no public
    read. Access only via `generate_presigned_url()`.
  - `upload_local()` — local filesystem fallback with the same structure.
- `Document` model extended: `file_size`, `file_mime_type`, `encryption_algorithm`,
  `file_url` columns.
- `upload_file_to_storage()` now: encrypts → stores to R2 private bucket (or local
  fallback) → persists the storage key + metadata linkage in the database.
- `GET /api/v1/onboarding/storage/status` — reports backend, encryption status,
  bucket, and storage structure.
- Frontend: no UI change (storage is transparent), but upload responses now
  include encryption + storage metadata.

> Environment: without R2 credentials the app falls back to local encrypted
> storage. Set `R2_*` vars in `.env` to switch to Cloudflare R2 (private bucket).
> A dedicated `STORAGE_ENCRYPTION_KEY` can override the derived key.

### US05 — Document Status Tracking
- Statuses `pending | uploaded | completed | missing` enforced by the
  `DocumentStatus` enum (already present from US01) and exposed everywhere.
- `PATCH /api/v1/onboarding/document/{id}/status` — transition a document's
  status (`{ "status": "completed" }`); validates the value and stores it.
- `GET /api/v1/onboarding/progress/{onboarding_id}` — completion stats:
  `completion_percentage`, `completed_documents`, `pending_documents`,
  `missing_documents`, `total_documents`.
- Uploading a file automatically sets the document to `uploaded` (US03).
- When **all** documents reach `uploaded`/`completed`, the onboarding is
  auto-marked `completed` with `completed_at` timestamp.
- The candidate portal response now includes `completion_percentage`,
  `completed_documents`, and `total_documents`; the frontend progress card
  uses these server values and shows missing counts.
- Frontend: progress card now displays "X of Y submitted · N missing" and
  switches to green at 100%.

### US06 — HR Onboarding Creation
- `get_current_user` dependency (core/security.py): OAuth2 Bearer JWT auth;
  returns the HR user or raises 401. Applied to all candidate/onboarding
  creation routes.
- `POST /api/v1/candidates/` — create a candidate (`full_name`, `email`,
  `phone`, `position`); requires HR JWT; duplicate email → **409**.
- `POST /api/v1/onboarding/{candidate_id}` — create an onboarding for an
  existing candidate; requires HR JWT; optional JSON body with custom
  `required_documents`; unknown candidate → **404**, duplicate onboarding →
  **409**.
- `POST /api/v1/onboarding/create-full` — combined convenience endpoint:
  creates candidate + onboarding (+ documents) in one request; requires HR
  JWT; returns `candidate`, `onboarding`, and seeded `documents`.
- Document seeding policy (documented in `onboarding_service.py`):
  - `required_documents` omitted → the 4 default documents are seeded.
  - `required_documents` provided → they **replace** the defaults entirely
    (HR defines the full checklist explicitly — appending could silently
    duplicate defaults). Each item supports `name`, `description`,
    `instructions`, `accepted_formats`, `required`.
- New onboardings always start as `pending` (unchanged US01 behavior).
- Frontend: new page `src/pages/CreateOnboardingPage.jsx` at route
  `/admin/onboarding/new` — candidate info form, checkbox list of the 4
  default docs plus add/remove custom document builder, loading/success/error
  states, and a post-submit summary view of the created onboarding.

### US07 — Invitation Email
- `app/services/email_service.py` (new):
  - Inline Jinja2 template (HTML + plain-text fallback) — no external template
    files. Includes candidate name, company/position context, the secure
    portal link (`FRONTEND_URL` + magic token), an expiry notice based on
    `MAGIC_TOKEN_EXPIRE_HOURS`, and the list of documents to prepare.
  - `is_email_configured()` — mirrors the R2 fallback pattern in storage.py:
    when `RESEND_API_KEY` is absent the send is skipped with a logged warning
    and status `not_sent` (no crash).
  - `send_invitation()` — renders the email, sends via the Resend SDK, and
    returns a typed result (`status`, `sent_at`, `last_error`, `portal_url`,
    `expiry_hours`). Provider errors (invalid recipient, rate limit, API
    failure) are caught and recorded as `failed` with `last_error` — the API
    responds 200 with `status: failed` instead of a raw 500.
  - Reuses a still-valid unused magic token from US01 instead of regenerating.
- `InvitationEmailStatus` enum (models.py): `not_sent | sent | failed |
  delivered | bounced` — defined consistently with `DocumentStatus`.
- `Onboarding` model extended: `invitation_sent_at`, `invitation_email_status`,
  `invitation_last_error`.
- `POST /api/v1/onboarding/{onboarding_id}/send-invitation` (HR auth):
  generates a magic link if missing/expired/used (or reuses a valid unused
  one), sends the email, updates the tracking fields, and returns delivery
  status + portal link + expiry for HR reference.
- `GET /api/v1/onboarding/{onboarding_id}/invitation-status` (HR auth):
  returns current tracking fields (status, sent_at, last_error) without
  resending — for polling/display.
- Webhook: not implemented in this MVP iteration. `delivered`/`bounced`
  tracking requires configuring a webhook in Resend's dashboard pointing at a
  future `POST /api/v1/webhooks/resend` endpoint; until then status rests at
  `sent`/`failed`.
- Frontend: "Send Invitation" button on the onboarding summary view
  (CreateOnboardingPage) with loading/success/error states, invitation status
  display, and the portal link shown for manual copy/share fallback.

### US08 — Automated Reminder System
- **Architecture**: Celery 5 + Redis (provisioned since the start of the
  project, reserved for this epic) is now wired up:
  - `app/core/celery_app.py` — Celery instance bound to
    `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` (the existing redis
    service), JSON serialization, UTC. Beat schedule:
    `scan_and_send_reminders` every `REMINDER_SCAN_INTERVAL_MINUTES`
    (default 60 → hourly).
  - `app/tasks/reminder_tasks.py` — the periodic scan task: pulls incomplete
    onboardings, applies the reminder rules, sends where due, and writes a
    `ReminderLog` row for **every** attempt (sent / failed / skipped).
    Per-onboarding failures are caught so one bad row can't kill the scan;
    the task also autoretries on unexpected errors (3×, 30 s backoff).
  - `docker-compose.yml` — new `celery-worker` and `celery-beat` services,
    same backend image/Dockerfile, codebase and `.env`; the existing
    db/redis/backend/frontend services are untouched.
- `app/services/reminder_service.py` (new):
  - `get_incomplete_onboardings()` — onboardings `pending`/`in_progress`
    with at least one document not in `uploaded`/`completed`.
  - Reminder rules (all thresholds read **live** from settings → US09 can
    expose them without code changes; safe defaults baked into
    `app/core/config.py`):
    - *midway*: once ≥50% (`REMINDER_MIDWAY_PERCENT`) of the token lifetime
      has elapsed since `invitation_sent_at` (fallback `created_at`), within
      the first half of the remaining lifetime.
    - *expiry_warning*: when < `REMINDER_EXPIRY_WINDOW_HOURS` (24 h) remain
      before `token_expires_at`.
    - *cap*: max `REMINDER_MAX_COUNT` (3) **sent** reminders per onboarding.
    - *cooldown*: min `REMINDER_COOLDOWN_HOURS` (24 h) between attempts of
      any kind (a failed attempt also starts a cooldown → no tight loops).
  - `send_reminder()` — reuses email_service's Resend integration; new
    reminder-specific template (HTML + plain-text) listing **only** the
    still-missing documents and the days left before link expiry. Same
    graceful fallback as US07: no `RESEND_API_KEY` → skipped + logged, no
    crash. `force=True` (manual HR trigger) bypasses cap/cooldown but is
    still audited.
- `ReminderLog` model (models.py): id, onboarding_id (FK, indexed), sent_at,
  status (`sent | failed | skipped` — `ReminderStatus` enum), reminder_type
  (`midway` / `expiry_warning`), reason (skip motive or provider error) —
  the persistent audit trail for reminder history.
- `GET /api/v1/onboarding/{onboarding_id}/reminders` (HR auth): full
  reminder history for one onboarding, oldest first.
- `POST /api/v1/onboarding/{onboarding_id}/send-reminder-now` (HR auth):
  manual trigger for testing/override — same `send_reminder()` path and
  identical logging as the scheduled task.

### US09 — Reminder Configuration
- **Scope decision (MVP)**: ONE global `ReminderConfig` row (singleton,
  `id=1`) — not per-onboarding overrides. One HR-tunable policy is all the
  MVP needs; overrides would add UI + precedence rules with no use case.
  The row is **auto-created from env-var defaults on first read** (no seed
  script); afterwards the row is authoritative and HR edits persist.
- `ReminderConfig` model (models.py), fields:
  - `reminder_frequency_hours` (24) — min interval between reminder
    *send attempts* (US08 cooldown now reads this).
  - `first_reminder_after_hours` (24) — quiet period after the invitation
    before the first reminder may fire (new gate in the rule engine).
  - `final_reminder_before_expiry_hours` (24) — expiry-warning window
    (US08 `REMINDER_EXPIRY_WINDOW_HOURS` now reads this).
  - `max_reminders_per_onboarding` (3) — cap on *sent* reminders.
  - `is_enabled` (true) — HR runtime kill switch; the env var
    `REMINDER_ENABLED` remains the deploy-level switch (both must be true).
  - Env vars `REMINDER_SCAN_INTERVAL_MINUTES` (celery-beat tick) and
    `REMINDER_MIDWAY_PERCENT` (midway fraction) stay deployment settings:
    beat reads its schedule at startup; the percentage is not an HR knob.
- `reminder_service.get_reminder_config()` — auto-create-on-first-read with
  graceful fallback to env-equivalent defaults if the row cannot be created;
  `apply_reminder_config()` — validation + persistence, single source of
  truth shared by the API and tests:
  `reminder_frequency_hours >= 1`, `first_reminder_after_hours >= 0`,
  `1 <= final_reminder_before_expiry_hours < MAGIC_TOKEN_EXPIRE_HOURS`,
  `max_reminders_per_onboarding >= 1`. Invalid PUTs are rejected with 422
  and leave the stored config untouched.
- `GET /api/v1/settings/reminders` (HR auth): current config — always
  returns a usable config (auto-creates defaults if none exists).
- `PUT /api/v1/settings/reminders` (HR auth): update config with the
  validation above.
- Frontend:
  - `src/pages/ReminderSettingsPage.jsx` at `/admin/settings/reminders` —
    form for all five fields, loads current values on mount, inline
    validation mirroring the backend rules, save with loading / success /
    error states, enable/disable kill-switch checkbox.
  - `src/components/ReminderHistory.jsx` — "Reminder History" section on
    the onboarding summary view (below the invitation panel): lists past
    reminders with status chips (sent/failed/skipped), type and timestamp,
    plus a "Send reminder now" button wired to the US08 manual trigger.
  - `src/utils/api.js` — `authFetch` helper: attaches the HR JWT from
    `localStorage.hr_token` (the MVP has no login UI yet; paste the token
    from `POST /api/v1/auth/login`).

### API endpoint summary

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Health check |
| POST | `/api/v1/auth/register` | Register HR user |
| POST | `/api/v1/auth/login` | HR login → JWT |
| POST | `/api/v1/candidates/` | Create candidate — **HR auth**, dup email → 409 |
| POST | `/api/v1/onboarding/create-full` | Combined create candidate + onboarding — **HR auth** (US06) |
| POST | `/api/v1/onboarding/{candidate_id}` | Create onboarding (+ optional custom docs) — **HR auth** (US06) |
| POST | `/api/v1/onboarding/{onboarding_id}/send-invitation` | Send invitation email (Resend) — **HR auth** (US07) |
| GET  | `/api/v1/onboarding/{onboarding_id}/invitation-status` | Invitation delivery status — **HR auth** (US07) |
| GET  | `/api/v1/onboarding/{onboarding_id}/reminders` | Reminder history (audit trail) — **HR auth** (US08) |
| POST | `/api/v1/onboarding/{onboarding_id}/send-reminder-now` | Manual reminder trigger — **HR auth** (US08) |
| GET  | `/api/v1/settings/reminders` | Read global reminder config — **HR auth** (US09) |
| PUT  | `/api/v1/settings/reminders` | Update global reminder config — **HR auth** (US09) |
| POST | `/api/v1/onboarding/magic-link` | Generate secure portal link |
| GET  | `/api/v1/onboarding/portal/{token}` | Validate token, open portal session |
| GET  | `/api/v1/onboarding/document/{id}` | Document upload context |
| POST | `/api/v1/onboarding/document/{id}/upload` | Upload file (PDF/image) |
| PATCH | `/api/v1/onboarding/document/{id}/status` | Update document status (US05) |
| GET  | `/api/v1/onboarding/progress/{onboarding_id}` | Completion % + counts (US05) |
| GET  | `/api/v1/onboarding/storage/status` | Storage backend + encryption status (US04) |

---

## 5. Configuration (`backend/.env`)

Copy `backend/.env.example` → `backend/.env` and set real values:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@db:5432/onboard_chaser` |
| `SECRET_KEY` | JWT signing key — **change in production** (`openssl rand -hex 32`) | dev placeholder |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | HR JWT lifetime | 60 |
| `MAGIC_TOKEN_EXPIRE_HOURS` | Candidate magic-link lifetime | 72 |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Cloudflare R2 credentials (US04) | empty → local fallback |
| `R2_BUCKET_NAME` | R2 bucket | `onboard-chaser-documents` |
| `R2_ENDPOINT_URL` | `https://<account_id>.r2.cloudflarestorage.com` | empty |
| `RESEND_API_KEY` / `EMAIL_FROM` | Resend email (US07) | empty |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis URLs (US08) | `redis://redis:6379/0` |
| `REMINDER_ENABLED` | Deploy-level kill switch for reminders (US08; HR also gets a runtime switch via US09 config) | `true` |
| `REMINDER_SCAN_INTERVAL_MINUTES` | celery-beat scan interval (US08; not an HR knob) | `60` |
| `REMINDER_MIDWAY_PERCENT` | Fraction of token lifetime before the midway reminder (US08; not an HR knob) | `0.5` |
| `REMINDER_EXPIRY_WINDOW_HOURS` | Default expiry-warning window — seeds the US09 config row | `24` |
| `REMINDER_COOLDOWN_HOURS` | Default reminder frequency — seeds the US09 config row | `24` |
| `REMINDER_MAX_COUNT` | Default reminder cap — seeds the US09 config row | `3` |
| `FRONTEND_URL` | Used to build magic links | `http://localhost:5173` |

> US09 note: after the first read, the `ReminderConfig` DB row (managed by HR
> at `/admin/settings/reminders` or `PUT /api/v1/settings/reminders`) is
> authoritative for frequency, first-reminder delay, expiry window, cap and
> the runtime kill switch; the `REMINDER_*` env vars above only seed that row
> and provide fallbacks if the row cannot be created.

---

## 6. Database Model

```
users (id UUID PK, email UNIQUE, full_name, hashed_password, is_hr, created_at)
  │
  │ 1 ── created_by
  ▼
candidates (id UUID PK, email UNIQUE, full_name, phone, position, created_by FK→users, created_at)
  │
  │ 1 ── 1
  ▼
onboardings (id UUID PK, candidate_id FK UNIQUE, status ENUM(pending|in_progress|completed),
             magic_token, token_expires_at, is_token_used, started_at, completed_at, created_at)
  │
  │ 1 ── N
  ▼
documents (id UUID PK, onboarding_id FK, name, description, instructions,
           required BOOL, accepted_formats, status ENUM(pending|uploaded|completed|missing),
           file_key, file_name, uploaded_at, created_at)
```

Tables are auto-created at startup via `Base.metadata.create_all()` (dev mode).
For production, switch to Alembic migrations (alembic is already pinned in
`requirements.txt`).

---

## 7. Development Workflow (Git Strategy)

One user story = one feature branch; branches are **not** auto-merged.

```
git checkout main && git pull
git checkout -b feature/<short-user-story-name>     # e.g. feature/document-upload
# ... implement task-by-task, run tests after each task ...
git add -A && git commit -m "feat: ..."            # conventional commits
git push -u origin feature/<short-user-story-name>
# present report → human approves → merge into main → delete branch
```

Conventional-commit prefixes used: `feat:`, `fix:`, `chore:`.

---

## 8. Security Notes (current MVP state)

- Candidate access is via **signed, expiring magic tokens** (JWT HS256, `type=magic`,
  `jti`, expiry). Tokens are validated server-side on every portal access; used
  tokens are flagged `is_token_used`.
- Passwords are hashed with **bcrypt** (passlib).
- Uploads are validated by size, non-emptiness, extension, and MIME consistency
  before hitting storage.
- R2 bucket should be **private** (public access disabled) — file downloads
  through signed URLs are planned in US04/US11.
- File content encryption-at-rest in R2 is a US04 task.
- The `.env` file is git-ignored; only `.env.example` is committed.

---

## 9. Roadmap (next stories)

1. **US10–11 — HR dashboard** (progress list, document preview/download).
2. **US12 — AI document verification:** Post-MVP, out of scope for now.
