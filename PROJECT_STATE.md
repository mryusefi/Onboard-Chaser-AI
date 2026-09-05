# Onboard Chaser AI MVP — Project State (for session handoff)

## Trigger: when user says "onboard chaser AI MVP" in a new session, load this file first.

---

## Location
- Project root: `E:\Onboard Chaser AI\MVP_Project`
- GitHub: `https://github.com/mryusefi/Onboard-Chaser-AI.git`

## Current Git State
- **Branch:** `feature/hr-dashboard` (US10; stacked on US09 → US08 — none merged)
- **Latest commit:** `124e8e3 chore: README for US10 (story table, US10 section, admin routes, endpoint, test count)`
- **Status:** US08+US09+US10 committed on their feature branches; US08/US09 pushed; US10 push pending
- **Tests:** 160 passing (US01:12, US02:11, US03:18, US04:12, US05:14, US06:17, US07:6, US08:31, US09:17, US10:21)
- Frontend build verified (`npx vite build`, 1577 modules, exit 0)

## Completed User Stories (US01–US07)
All merged to main via feature branches. Plane epic + sub-tasks for each marked Done.

## Next Story: US11
- **Epic:** US08–10 — DONE (reminders, config, HR dashboard)
- **US08 status:** COMPLETE on `feature/automated-reminders` (pushed)
- **US09 status:** COMPLETE on `feature/reminder-config` (pushed)
- **US10 status:** COMPLETE on `feature/hr-dashboard` (commit + push this session)
- Merge order when approved: US08 → US09 → US10 (strictly stacked).
- **US11 work:** extend `/admin/onboarding/:id`
  (`frontend/src/pages/OnboardingDetailPage.jsx` — placeholder already shows
  candidate + progress + ReminderHistory) with document-level detail:
  per-document status/files, preview/download via `generate_presigned_url`,
  and status controls reusing `update_document_status`. Backend needs an
  HR-authenticated `GET /api/v1/onboarding/{onboarding_id}/detail` returning
  full document rows (the US10 list endpoint deliberately returns counts only).

## US09 — What Was Built (branch `feature/reminder-config`)
- Scope decision (documented in models.py + README): ONE global ReminderConfig
  singleton row (id=1), auto-created from REMINDER_* env defaults on first
  read; row is authoritative afterwards. NOT per-onboarding overrides.
- `ReminderConfig` model (models.py): reminder_frequency_hours (cooldown),
  first_reminder_after_hours (NEW quiet-period gate),
  final_reminder_before_expiry_hours (expiry window),
  max_reminders_per_onboarding (cap), is_enabled (HR runtime kill switch;
  env REMINDER_ENABLED stays deploy-level switch — both must be true).
- reminder_service: get_reminder_config() (auto-create + graceful fallback),
  apply_reminder_config() (validation shared by API/tests); rule engine
  evaluate_reminder_rules() now has 7 gates reading live config values.
- API (HR auth): GET/PUT /api/v1/settings/reminders in NEW app/api/settings.py
  (imported ALIASED in main.py — `from app.api import settings` would shadow
  app.core.config.settings). Invalid PUT -> 422, config untouched.
  Validation: freq>=1, first>=0, 1<=final<MAGIC_TOKEN_EXPIRE_HOURS, max>=1.
- Frontend: src/pages/ReminderSettingsPage.jsx at /admin/settings/reminders
  (form, load/save states, inline validation, kill switch);
  src/components/ReminderHistory.jsx on the onboarding summary view
  (status chips + "Send reminder now" button); src/utils/api.js authFetch
  helper (reads localStorage.hr_token — no login UI exists yet).
- Frontend build verified: `npx vite build` OK (1574 modules).
- Tests: tests/test_us09.py — 17 tests (GET defaults + auto-create +
  idempotency, PUT happy paths, 5 validation cases incl. final>=lifetime,
  auth on both endpoints, live-config integration: cooldown/disable/
  re-enable/first-delay/send-blocked).

## US08 — What Was Built (branch `feature/automated-reminders`)
- `backend/app/core/celery_app.py` — Celery app wired to CELERY_BROKER_URL /
  CELERY_RESULT_BACKEND (redis://redis:6379/0); beat entry
  `scan-and-send-reminders` every REMINDER_SCAN_INTERVAL_MINUTES*60 s.
- `backend/app/tasks/reminder_tasks.py` — `scan_and_send_reminders`: hourly
  scan; every attempt (sent/failed/skipped) writes a ReminderLog; per-row
  errors caught; autoretry 3× with 30 s backoff. Uses `_session_factory()`
  indirection so tests can inject the SQLite session.
- `backend/app/services/reminder_service.py` — get_incomplete_onboardings(),
  evaluate_reminder_rules() (midway/expiry_warning/cap/cooldown, read live
  from settings), send_reminder() (force flag for manual HR trigger).
- Reminder templates in `email_service.py` (render_reminder_email /
  render_reminder_plain_text) — distinct from invitation template; lists only
  missing docs + days left; same no-Resend-key fallback (skipped, no crash).
- `ReminderLog` model + `ReminderStatus` enum in models.py; Onboarding.
  reminder_logs relationship.
- API (HR auth): GET `/{onboarding_id}/reminders`,
  POST `/{onboarding_id}/send-reminder-now` in `api/onboarding.py`; schemas
  `ReminderLogResponse`, `ReminderSendResponse` in schemas.py.
- docker-compose.yml: `celery-worker` + `celery-beat` services (same backend
  image/.env/volume; db/redis/backend/frontend untouched; validated with
  `docker compose config`).
- Config knobs (in config.py + .env.example): REMINDER_ENABLED,
  REMINDER_SCAN_INTERVAL_MINUTES, REMINDER_MIDWAY_PERCENT,
  REMINDER_EXPIRY_WINDOW_HOURS, REMINDER_COOLDOWN_HOURS, REMINDER_MAX_COUNT.
- Tests: `tests/test_us08.py` — 31 tests (selection, rules, cap/cooldown,
  endpoints incl. auth/404/400, celery wiring, end-to-end scan).

## US08 — Verification Notes / Gaps
- Full suite green: 122 passed locally (in-memory SQLite, no Docker needed).
- Celery app boot verified: broker/backend URLs, beat interval 3600 s, task
  registered and matches the beat entry.
- Docker daemon was NOT running on this host, so worker/beat were not
  exercised against a live Redis. When Docker is up:
  `docker compose up -d db redis backend celery-worker celery-beat` then
  `docker compose logs celery-worker` after a beat tick.

## Architecture (unchanged since session 1)
- Backend: FastAPI + SQLAlchemy + Pydantic v2 + python:3.11-slim-bookworm (Docker)
- Frontend: React + Vite + Tailwind (node:20-alpine Docker)
- DB: PostgreSQL 16 (host port 5433, Docker port 5432)
- Redis: Redis 7 (host port 6380, Docker port 6379)
- Storage: Cloudflare R2 private bucket (local AES-256-Fernet fallback)
- Email: Resend SDK (is_email_configured() fallback, RESEND_API_KEY absent → not_sent)
- Auth: JWT (HR via get_current_user dependency) + magic links (candidates)
- Compose: `docker compose up -d` in project root

## Key Files / Patterns
- `backend/app/core/security.py` — get_current_user (HR JWT), create_magic_token, decode_access_token
- `backend/app/core/config.py` — all Settings, env vars (RESEND_API_KEY, R2_*, etc.)
- `backend/app/models/models.py` — User, Candidate, Onboarding, Document, + OnboardingStatus, DocumentStatus, InvitationEmailStatus enums
- `backend/app/schemas/schemas.py` — all Pydantic schemas including FullOnboardingCreate, OnboardingCreate, RequiredDocumentCreate, CandidateOnboardingResponse, InvitationEmailStatus (the enum-like model)
- `backend/app/services/onboarding_service.py` — create_candidate (409 dup), create_onboarding_for_candidate (custom docs replace defaults), create_full_onboarding, generate_magic_link, validate_candidate_access, compute_completion_percentage, update_document_status
- `backend/app/services/document_service.py` — validate_file, upload_file_to_storage (encrypts → R2/local, persists linkage)
- `backend/app/services/storage.py` — is_r2_configured (rejects placeholders), encrypt_bytes/decrypt_bytes, upload_to_r2, upload_local, generate_presigned_url, storage_path_for
- `backend/app/services/email_service.py` — render_invitation_email (Jinja2 inline template), render_plain_text, is_email_configured, send_invitation (magic link reuse, Resend fallback)
- `backend/app/api/onboarding.py` — /create-full (before /{candidate_id}!), /{candidate_id}, /magic-link, /portal/{token}, /document/{id}, /document/{id}/upload, /document/{id}/status, /progress/{id}, /storage/status, /{id}/send-invitation, /{id}/invitation-status
- `backend/app/api/candidates.py` — POST /candidates/ (HR auth, 409 dup)
- `backend/app/api/auth.py` — POST /auth/register, POST /auth/login (UserLogin schema)
- `backend/tests/conftest.py` — in-memory SQLite, TestingSession, hr_headers fixture, make_hr_headers()
- `frontend/src/App.jsx` — routes: /, /onboard/:token, /admin/onboarding/new
- `frontend/src/pages/CreateOnboardingPage.jsx` — candidate form + doc picker + InvitationPanel (US07 send button + status)
- `frontend/src/pages/OnboardingPortal.jsx` — candidate portal (docs, upload, progress)
- `frontend/src/pages/HomePage.jsx` — landing page
- `frontend/vite.config.js` — proxy to VITE_API_URL || localhost:8000

## Docker Compose Ports
| Service  | Host Port | Container Port |
|----------|-----------|----------------|
| db       | 5433      | 5432           |
| redis    | 6380      | 6379           |
| backend  | 8000      | 8000           |
| frontend | 5173      | 5173           |

## Running the Project
```bash
cd "E:\Onboard Chaser AI\MVP_Project"
docker compose up -d        # starts all 4 services
docker compose down          # stops
# Or for local dev (no Docker):
cd backend && pip install -r requirements.txt && DATABASE_URL="postgresql://postgres:***@localhost:5433/onboard_chaser" uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

## Test Command
```bash
cd "E:\Onboard Chaser AI/MVP_Project/backend"
TESTING=1 python -m pytest tests/ -q
# Expected: 160 passed (US01:12, US02:11, US03:18, US04:12, US05:14, US06:17, US07:6, US08:31, US09:17, US10:21)
```

## Work Convention (must follow)
- One user story = one feature branch (`feature/<short-name>`)
- Commit after each task with conventional commits (feat:/fix:/chore:)
- After writing tests, run full suite to confirm nothing broke
- **DO NOT auto-merge** into main
- **DO NOT push** unless explicitly told
- **DO NOT touch Plane** unless explicitly told
- Only modify files relevant to the active user story
- Follow existing patterns in app/api, app/services, app/schemas, app/models

## README Update Convention
After finishing a US:
- Story table row → mark done, add branch name + test count
- Add "### US## — Title" section before "### API endpoint summary"
- API endpoint summary table → add new/changed endpoints with US tag
- Test count in "Run the tests" → update total
- Don't rewrite unrelated parts

## What Does NOT Exist Yet (post-10 gaps)
- US11: Onboarding/document detail view (entry point `/admin/onboarding/:id`
  placeholder ready; backend detail endpoint with full document rows needed)
- US12: AI document verification (out of scope)
- No login UI (only API endpoints for register/login; frontend authFetch
  expects the HR JWT in localStorage.hr_token)
- Docker runtime verification of celery-worker/celery-beat pending (daemon was
  down during the US08–US10 sessions)

## Readme (master document)
- README.md is comprehensive: architecture diagram, project structure, how to run (Docker + local), US01–US07 sections, full API table, config table, test instructions
- After each US completion, README is updated per conventions above

## Key Decisions Already Made
- Custom required_documents REPLACE defaults (not append) — documented in onboarding_service.py
- /create-full registered BEFORE /{candidate_id} to prevent path shadowing
- is_r2_configured() rejects placeholder values ("your_*")
- Email fallback: RESEND_API_KEY absent → status "not_sent", logged, no crash
- Provider errors caught in email service → status "failed" with last_error, API returns 200 not 500
- Magic token reuse: send_invitation reuses valid unused token instead of regenerating
- is_email_configured() mirrors is_r2_configured() pattern

## Plane
- Workspace: techco, Project ID: a704d29d-7ff5-474a-85df-3769c81a66af
- API Key: plane_api_c38da3d4d29f40428c2a15580558c445
- US01-US07: all Done (epics + sub-tasks)
