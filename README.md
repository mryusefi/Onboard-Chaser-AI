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
├── docker-compose.yml            # Full stack orchestration
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example              # Copy to .env and fill in secrets
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router registration
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic-settings (reads .env)
│   │   │   ├── database.py       # SQLAlchemy engine/session
│   │   │   └── security.py       # JWT + magic-link tokens, bcrypt
│   │   ├── models/models.py      # SQLAlchemy ORM: User, Candidate, Onboarding, Document
│   │   ├── schemas/schemas.py    # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── auth.py           # POST /auth/register, /auth/login
│   │   │   ├── candidates.py     # POST /candidates/
│   │   │   └── onboarding.py     # onboarding + document endpoints
│   │   └── services/
│   │       ├── onboarding_service.py  # create onboarding, magic links, portal session
│   │       └── document_service.py    # file validation, R2 upload, metadata
│   └── tests/
│       ├── conftest.py           # shared in-memory SQLite test DB + fixtures
│       ├── test_us01.py          # 12 tests — secure portal
│       ├── test_us02.py          # 11 tests — document checklist
│       └── test_us03.py          # 18 tests — document upload
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js            # dev server + /api proxy → backend:8000
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx              # React entry, BrowserRouter
        ├── App.jsx               # Routes: / and /onboard/:token
        ├── index.css             # Tailwind + gradient helper
        └── pages/
            ├── HomePage.jsx              # Landing page
            └── OnboardingPortal.jsx      # Checklist + upload UI
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

# 3. Build & start all services (db, redis, backend, frontend)
docker compose up --build

# 4. Verify
#    Backend health:  http://localhost:8000/health   → {"status":"healthy"}
#    API docs:        http://localhost:8000/docs     (Swagger UI)
#    Frontend:        http://localhost:5173
#    DB:              postgres://postgres:postgres@localhost:5432/onboard_chaser
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
#   export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/onboard_chaser"
# (or put it in backend/.env)

uvicorn app.main:app --reload --port 8000
# API: http://localhost:8000  |  Docs: http://localhost:8000/docs

# --- Frontend (second terminal) ---
cd frontend
npm install
npm run dev
# App: http://localhost:5173
# Vite proxies /api → http://backend:8000 (Docker DNS name).
# For local dev without Docker, change vite.config.js proxy target to
# http://localhost:8000 (or set VITE_API_URL).
```

### Run the tests

```bash
cd backend
TESTING=1 python -m pytest tests/ -v
# Expected: 54 passed (US01: 12, US02: 11, US03: 18, US04: 12)
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
| US05  | Document status tracking | ⏳ Backlog | — | — |
| US06–07 | HR onboarding creation + email invites | ⏳ Backlog | — | — |
| US08–09 | Automated reminders + config | ⏳ Backlog | — | — |
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

### API endpoint summary

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Health check |
| POST | `/api/v1/auth/register` | Register HR user |
| POST | `/api/v1/auth/login` | HR login → JWT |
| POST | `/api/v1/candidates/` | Create candidate (US06 foundation) |
| POST | `/api/v1/onboarding/{candidate_id}` | Create onboarding + default docs |
| POST | `/api/v1/onboarding/magic-link` | Generate secure portal link |
| GET  | `/api/v1/onboarding/portal/{token}` | Validate token, open portal session |
| GET  | `/api/v1/onboarding/document/{id}` | Document upload context |
| POST | `/api/v1/onboarding/document/{id}/upload` | Upload file (PDF/image) |

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
| `FRONTEND_URL` | Used to build magic links | `http://localhost:5173` |

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

1. **US04 — Secure document storage (R2):** private bucket config, folder
   structure, server-side encryption, DB↔storage linkage.
2. **US05 — Document status tracking:** completed/missing transitions,
   completion percentage.
3. **US06 — HR creates onboarding:** candidate info form + required docs picker.
4. **US07 — Invitation email via Resend** with the secure portal link.
5. **US08–09 — Automated reminders (Celery + Redis)** and reminder config.
6. **US10–11 — HR dashboard** (progress list, document preview/download).
7. **US12 — AI document verification:** Post-MVP, out of scope for now.
