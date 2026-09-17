# Item 1 — diagnosis report (verified, not assumed)

## What I checked
1. `backend/.env` (the file actually mounted into the container via
   docker-compose `env_file`) — read character-by-character:
   - `RESEND_API_KEY=re_your_api_key_here`  ← PLACEHOLDER, not a real key
   - `EMAIL_FROM=onboarding@onboardchaser.ai` (set, fine)
2. Container environment: `docker compose exec backend printenv RESEND_API_KEY`
   → `re_your_api_key_here` (same placeholder; compose injects it).
3. `email_service.is_email_configured()` = `bool(os.getenv("RESEND_API_KEY"))`
   → the placeholder is non-empty ⇒ returns **True** (the "not configured"
   path does NOT trigger — a placeholder slips past the check).
4. Live end-to-end probe through the API (register → login → create-full →
   send-invitation):
   `status: "failed"`, `last_error: "module 'resend' has no attribute 'send'"`
5. SDK check inside the container (resend==2.0.0): the SDK has **no module
   function `resend.send`** — that was the OLD 0.x/1.x API. 2.0.0 requires
   `resend.api_key = <key>` + `resend.Emails.send(params_dict)`.

## Conclusion (two stacked real causes, neither was "per-user")
- CAUSE A (code bug): `_send_resend()` calls `resend.send(...)`, which doesn't
  exist in the pinned SDK version → EVERY send fails with 500-class
  AttributeError, regardless of who's logged in or whether a real key exists.
- CAUSE B (config): the only key present is the `re_your_api_key_here`
  placeholder, which `is_email_configured()` can't distinguish from a real
  key → even after fixing CAUSE A, Resend replies "API key is invalid"
  (verified by calling `Emails.send` with a fake key inside the container:
  `ResendError: API key is invalid`).
- The user-visible message ("Invitation failed — check RESEND_API_KEY") came
  from the frontend mapping `status: failed` generically — it conflates
  "not configured" with "provider rejected the send".
