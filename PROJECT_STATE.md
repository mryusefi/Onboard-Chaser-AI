# Onboard Chaser AI MVP — Project State (for session handoff)

## Trigger: when user says "onboard chaser AI MVP" in a new session, load this file first.

---

## Location
- Project root: `E:\Onboard Chaser AI\MVP_Project`
- GitHub: `https://github.com/mryusefi/Onboard-Chaser-AI.git`

## Current Git State
- **Branch:** `main` (synced with `origin/main`)
- **Latest commit:** `7dc2382 Merge pull request #7 from feature/invitation-email`
- **Status:** Clean, no uncommitted changes, up to date with remote
- **Tests:** 91 passing (US01:12, US02:11, US03:18, US04:12, US05:14, US06:17, US07:6)

## Completed User Stories (US01–US07)
All merged to main via feature branches. Plane epic + sub-tasks for each marked Done.

## Next Story: US08
- **Epic:** US08–09 — Automated reminders + config
- **Plane epic ID:** (not critical; look it up fresh in Plane)

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
# Expected: 91 passed (US01:12, US02:11, US03:18, US04:12, US05:14, US06:17, US07:6)
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

## What Does NOT Exist Yet (post-07 gaps)
- US08-09: Automated reminders (Celery + Redis broker in deps/compose, no worker or task scheduled)
- US10-11: HR dashboard / candidate list view / onboarding list / document detail view
- US12: AI document verification (out of scope)
- No login UI (only API endpoints for register/login)
- No admin shell / navigation from HomePage to admin pages

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
