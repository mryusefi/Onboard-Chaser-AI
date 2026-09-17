"""Email service for US07 with inline Jinja2 template (no external template files needed)."""
import os
from typing import Optional
from uuid import UUID

from jinja2 import Environment, BaseLoader, select_autoescape

from app.core.config import settings

# ────────────────────────────────────────────────────────────────────────
# 1️⃣ Template + rendering helpers
# ────────────────────────────────────────────────────────────────────────
# We keep the template as a single multi-line string so there is *no* file to
# create outside the repo.  The Jinja2 Environment is created once at import time
# so there is no runtime penalty.
EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {font-family:system-ui,system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
          margin:0;background:#f7f9fc;line-height:1.5;color:#1e293b}
    .wrapper {max-width:600px;margin:0 auto;background:#fff;padding:32px 24px;border-radius:12px;
              box-shadow:0 4px 12px rgba(0,0,0,0.04)}
    .header {text-align:center;padding-bottom:24px;border-bottom:1px solid #e2e8f0}
    .header h1 {font-size:24px;margin:0;color:#1e293b}
    .content {margin-top:24px}
    .bullet {margin:8px 0;padding-left:16px;list-style:none}
    .bullet li {position:relative}
    .bullet li:before {content:"•";position:absolute;left:0;color:#64748b}
    .footer {margin-top:24px;font-size:12px;color:#64748b;text-align:center}
    .footer a {color:#64748b;text-decoration:none}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Welcome to {{ company_name }}</h1>
    </div>

    <p>
      {% if body_intro %}{{ body_intro }}{% else %}Hello {{ candidate_name }},
      You have been invited to complete onboarding for <strong>{{ company_name }}</strong>.
      Your position is <strong>{{ position }}</strong>.{% endif %}
    </p>

    {% if extra_instructions %}
    <p class="bullet"><strong>Note from our HR team:</strong></p>
    <p class="bullet">{{ extra_instructions }}</p>
    {% endif %}

    <p>Below is a <strong>secure portal link</strong> that will expire after
    <strong>{{ expiry_hours }} hour{% if expiry_hours != 1 %}s{% endif %}</strong>.</p>

    <p style="margin-top:24px">
      <a href="{{ portal_url }}" target="_blank"
         style="background:#3b82f6;color:#fff;padding:12px 24px;border-radius:6px;
              font-weight:600;text-decoration:none">
        Start onboarding
      </a>
    </p>

    <p class="bullet">
      <strong>What you’ll need to prepare:</strong>
    </p>
    <ul class="bullet">
      {% for doc in docs %}
        <li>{{ doc.name }}{% if doc.instructions %}: {{ doc.instructions }}{% endif %}</li>
      {% endfor %}
    </ul>

    {% if body_closing %}
    <p style="margin-top:24px">{{ body_closing }}</p>
    {% else %}
    <p style="margin-top:24px">
      If you have any questions, reply to this email or contact our HR team.
    </p>
    {% endif %}
  </div>
</body>
</html>
"""

_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(["html"]),
)


def render_invitation_email(
    candidate_name: str,
    company_name: str,
    position: Optional[str],
    portal_url: str,
    expiry_hours: int,
    docs: list[dict],
    template_config: Optional[dict] = None,
) -> str:
    """
    Render the invitation e-mail HTML (and plain-text fallback below).

    Maintenance pass Item 1b: ``template_config`` (from the
    EmailTemplateConfig singleton, when HR customized it) overrides the
    SAFE-TO-EDIT copy only — subject line, greeting/intro, closing, extra
    instructions. The functional parts (portal link, document list, expiry
    notice) are ALWAYS injected here and can not be removed by config.
    """
    cfg = template_config or {}
    return _env.from_string(EMAIL_TEMPLATE).render(
        candidate_name=candidate_name,
        company_name=company_name or "Onboard Chaser AI",
        position=position or "",
        portal_url=portal_url,
        expiry_hours=expiry_hours,
        docs=docs,
        subject_template=cfg.get("subject_template"),
        body_intro=cfg.get("body_intro"),
        body_closing=cfg.get("body_closing"),
        extra_instructions=cfg.get("extra_instructions"),
    )


def render_plain_text(
    candidate_name: str,
    company_name: str,
    position: Optional[str],
    portal_url: str,
    expiry_hours: int,
    docs: list[dict],
    template_config: Optional[dict] = None,
) -> str:
    """
    Very small plain-text fallback so clients that reject HTML still work.
    Item 1b: honors the HR-editable copy (subject/intro/closing/extra
    instructions) exactly like the HTML render; functional parts stay fixed.
    """
    cfg = template_config or {}
    lines = []
    if cfg.get("body_intro"):
        lines.append(cfg["body_intro"])
    else:
        lines.append(f"Hello {candidate_name},")
        lines.append(f"You have been invited to complete onboarding for {company_name or 'Onboard Chaser AI'}.")
    if position:
        lines.append(f"Your position is {position}.")
    if cfg.get("extra_instructions"):
        lines.append(cfg["extra_instructions"])
    lines += [
        f"Secure portal link: {portal_url}",
        f"This link will expire in {expiry_hours} hour{'' if expiry_hours == 1 else 's'}.",
        "",
        "What you'll need to prepare:",
    ]
    for doc in docs:
        name = doc.get("name", "Document")
        instr = doc.get("instructions")
        line = f"- {name}"
        if instr:
            line += f": {instr}"
        lines.append(line)
    lines += [""]
    if cfg.get("body_closing"):
        lines.append(cfg["body_closing"])
    else:
        lines.append("If you have any questions, reply to this email or contact our HR team.")
    lines.append(f"Portal URL (copy & share): {portal_url}")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────
# US08 — Reminder e-mail templates (distinct from the invitation template)
# ────────────────────────────────────────────────────────────────────────
REMINDER_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {font-family:system-ui,system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
          margin:0;background:#f7f9fc;line-height:1.5;color:#1e293b}
    .wrapper {max-width:600px;margin:0 auto;background:#fff;padding:32px 24px;border-radius:12px;
              box-shadow:0 4px 12px rgba(0,0,0,0.04)}
    .header {text-align:center;padding-bottom:24px;border-bottom:1px solid #e2e8f0}
    .header h1 {font-size:22px;margin:0;color:#1e293b}
    .badge {display:inline-block;background:#fef3c7;color:#92400e;font-size:12px;
            font-weight:600;padding:4px 12px;border-radius:999px;margin-top:12px}
    .badge.urgent {background:#fee2e2;color:#991b1b}
    .content {margin-top:24px}
    .bullet {margin:8px 0;padding-left:16px;list-style:none}
    .bullet li {position:relative}
    .bullet li:before {content:"•";position:absolute;left:0;color:#64748b}
    .footer {margin-top:24px;font-size:12px;color:#64748b;text-align:center}
    .footer a {color:#64748b;text-decoration:none}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Your onboarding is still incomplete</h1>
      <span class="badge{% if urgent %} urgent{% endif %}">
        {{ days_left }} day{% if days_left != 1 %}s{% endif %} left to complete it
      </span>
    </div>

    <p>Hello {{ candidate_name }},</p>

    <p>This is a friendly reminder about your onboarding for
    <strong>{{ company_name }}</strong>{% if position %} (<strong>{{ position }}</strong>){% endif %}.
    You still have <strong>{{ doc_count }} document{{ '' if doc_count == 1 else 's' }}</strong>
    to submit.</p>

    <p class="bullet"><strong>Still missing:</strong></p>
    <ul class="bullet">
      {% for doc in docs %}
        <li>{{ doc.name }}{% if doc.instructions %}: {{ doc.instructions }}{% endif %}</li>
      {% endfor %}
    </ul>

    <p>Your secure portal link expires in
    <strong>{{ days_left }} day{% if days_left != 1 %}s{% endif %}</strong>.</p>

    <p style="margin-top:24px">
      <a href="{{ portal_url }}" target="_blank"
         style="background:#3b82f6;color:#fff;padding:12px 24px;border-radius:6px;
              font-weight:600;text-decoration:none">
        Continue onboarding
      </a>
    </p>

    <p style="margin-top:24px">
      If you have any questions, reply to this email or contact our HR team.
    </p>
  </div>
</body>
</html>
"""


def render_reminder_email(
    candidate_name: str,
    company_name: str,
    position: Optional[str],
    portal_url: str,
    days_left: int,
    docs: list[dict],
) -> str:
    """Render the reminder e-mail HTML (US08) — lists only still-missing docs."""
    return _env.from_string(REMINDER_TEMPLATE).render(
        candidate_name=candidate_name,
        company_name=company_name or "Onboard Chaser AI",
        position=position or "",
        portal_url=portal_url,
        days_left=days_left,
        docs=docs,
        doc_count=len(docs),
        urgent=days_left <= 1,
    )


def render_reminder_plain_text(
    candidate_name: str,
    company_name: str,
    position: Optional[str],
    portal_url: str,
    days_left: int,
    docs: list[dict],
) -> str:
    """Plain-text fallback for the reminder e-mail (US08)."""
    lines = [
        f"Hello {candidate_name},",
        f"Reminder: your onboarding for {company_name or 'Onboard Chaser AI'} is still incomplete.",
        f"You still have {len(docs)} document{'' if len(docs) == 1 else 's'} to submit:",
    ]
    for doc in docs:
        name = doc.get("name", "Document")
        instr = doc.get("instructions")
        line = f"- {name}"
        if instr:
            line += f": {instr}"
        lines.append(line)
    lines += [
        "",
        f"Your secure portal link expires in {days_left} day{'' if days_left == 1 else 's'}.",
        f"Portal URL: {portal_url}",
        "",
        "If you have any questions, reply to this email or contact our HR team.",
    ]
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────
# 2️⃣ Resend SDK wrapper (maintenance pass: resend SDK 2.0 + placeholder
#    detection + granular config status for the settings page)
# ────────────────────────────────────────────────────────────────────────
# Values that look like keys but aren't: .env ships "re_your_api_key_here"
# which is non-empty, so a naive bool() check called it "configured" and the
# send then died inside the provider with "API key is invalid".
_PLACEHOLDER_KEY_VALUES = {"", "your_api_key_here", "change-me", "changeme"}


def _is_placeholder_key(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    if v.lower() in _PLACEHOLDER_KEY_VALUES:
        return True
    if v.lower().startswith("re_your"):
        return True
    return False


def _email_config_state() -> dict:
    """
    Single source of truth for email configuration status (maintenance pass
    Item 1): whether a REAL Resend key + from address are present. Never
    returns the key itself — only booleans + the from address.
    """
    import resend  # SDK presence is part of "configured"

    key = os.getenv("RESEND_API_KEY") or settings.RESEND_API_KEY or ""
    configured = bool(resend) and not _is_placeholder_key(key) and bool(settings.EMAIL_FROM)
    return {
        "resend_configured": configured,
        "email_from": settings.EMAIL_FROM or None,
    }


try:
    import resend  # type: ignore
    _resend_configured = not _is_placeholder_key(
        os.getenv("RESEND_API_KEY") or settings.RESEND_API_KEY or ""
    )
except Exception:  # pragma: no cover
    _resend_configured = False


def is_email_configured() -> bool:
    """
    True only when a REAL Resend API key is present (mirrors the R2
    placeholder-rejecting pattern in storage.py). The shipped placeholder
    `re_your_api_key_here` counts as NOT configured (maintenance pass fix —
    it previously slipped through and produced provider auth failures).
    """
    return _resend_configured


# Maintenance pass Item 1: single user-facing hint for "email not configured",
# reused by send_invitation's not_sent path and the /settings/email-status
# endpoints (so the UI message matches across all surfaces).
NOT_CONFIGURED_HINT = (
    "Email sending is not configured on this server. Ask your administrator "
    "to set RESEND_API_KEY and EMAIL_FROM in the backend environment."
)


def _send_resend(to: str, subject: str, html: str, text: str) -> dict:
    """
    Blocking call to Resend SDK; raises on provider error.

    Maintenance pass fix: resend==2.0.0 removed the module-level
    ``resend.send()`` used here before (it raised "module 'resend' has no
    attribute 'send'" for EVERY send). The 2.x API is:
        resend.api_key = ...
        resend.Emails.send({from, to: [..], subject, html, text})
    """
    if not _resend_configured:
        raise RuntimeError(
            "Email sending is not configured on this server. Ask your "
            "administrator to set RESEND_API_KEY and EMAIL_FROM in the "
            "backend environment."
        )
    resend.api_key = os.getenv("RESEND_API_KEY") or settings.RESEND_API_KEY
    params = {
        "from": settings.EMAIL_FROM,
        "to": [to],  # 2.x expects a list of recipients
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text
    msg = resend.Emails.send(params)
    return msg  # Email object/dataclass with .id etc.


# ────────────────────────────────────────────────────────────────────────
# 3️⃣ Public API used by the FastAPI route
# ────────────────────────────────────────────────────────────────────────
def _load_template_config(db) -> Optional[dict]:
    """
    Item 1b: load the HR-editable invitation copy (EmailTemplateConfig
    singleton). Returns None when no row exists -> callers fall back to the
    hardcoded template. Also used by the settings API (GET).
    """
    try:
        from app.models.models import EmailTemplateConfig
        row = db.query(EmailTemplateConfig).filter(EmailTemplateConfig.id == 1).first()
        if not row:
            return None
        return {
            "subject_template": row.subject_template,
            "body_intro": row.body_intro,
            "body_closing": row.body_closing,
            "extra_instructions": row.extra_instructions,
        }
    except Exception:  # table missing / DB not ready -> default template
        return None


def send_invitation(
    *,
    candidate_name: str,
    company_name: str,
    position: Optional[str],
    candidate_email: str,
    onboarding_id: UUID,
    db,  # sqlalchemy Session
) -> dict:
    """
    Render + send the invitation e‑mail (US07).

    Returns a dict with the following keys:
      - status: one of InvitationEmailStatus
      - sent_at: datetime or None
      - last_error: str or None
      - portal_url: the secure link the candidate will click
      - expiry_hours: the MAGIC_TOKEN_EXPIRE_HOURS value
    """
    from uuid import UUID
    from datetime import datetime, timezone, timedelta

    from app.core.security import create_magic_token, validate_magic_token
    from app.core.config import settings
    from app.models.models import Onboarding, Document, InvitationEmailStatus, EmailTemplateConfig
    from app.services.email_service import render_invitation_email, render_plain_text

    # ──① Ensure a valid magic link exists ───────────────────────────────
    onboarding = db.query(Onboarding).filter(Onboarding.id == onboarding_id).first()
    if not onboarding:
        raise ValueError("onboarding_not_found")

    # Re‑use the existing US01 magic‑link logic
    token = onboarding.magic_token
    if not token or not validate_magic_token(token):
        token = create_magic_token(str(onboarding.id), onboarding.candidate.email)
        onboarding.magic_token = token
        onboarding.token_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.MAGIC_TOKEN_EXPIRE_HOURS
        )
        db.commit()

    portal_url = f"{settings.FRONTEND_URL}/onboard/{token}"
    expiry_hours = settings.MAGIC_TOKEN_EXPIRE_HOURS

    # ──② Render e‑mail (HTML + plain-text) ─────────────────────────────
    docs = db.query(Document).filter(Document.onboarding_id == onboarding.id).all()
    docs_list = [
        {"name": d.name, "instructions": d.instructions, "accepted_formats": d.accepted_formats}
        for d in docs
    ]
    html = render_invitation_email(
        candidate_name=candidate_name,
        company_name=company_name,
        position=position,
        portal_url=portal_url,
        expiry_hours=expiry_hours,
        docs=docs_list,
        template_config=_load_template_config(db),
    )
    text = render_plain_text(
        candidate_name=candidate_name,
        company_name=company_name,
        position=position,
        portal_url=portal_url,
        expiry_hours=expiry_hours,
        docs=docs_list,
        template_config=_load_template_config(db),
    )

    # ──② Send via Resend (or graceful fallback) ────────────────────────
    result: dict = {
        "status": InvitationEmailStatus.NOT_SENT,
        "sent_at": None,
        "last_error": None,
        "portal_url": portal_url,
        "expiry_hours": expiry_hours,
    }

    if not is_email_configured():
        # Log, but **do not** raise – the API layer records `not_sent`.
        # Maintenance pass Item 1: the reason text now tells the HR admin
        # exactly what to do (deployment-level fix), instead of a generic
        # "check RESEND_API_KEY" that read like a per-user problem.
        import logging
        logging.getLogger(__name__).warning(
            "RESEND_API_KEY missing/placeholder – invitation e-mail not sent (not_sent)"
        )
        result["status"] = InvitationEmailStatus.NOT_SENT
        result["last_error"] = NOT_CONFIGURED_HINT
        return result

    try:
        # Item 1b: subject honors the HR-editable template when present.
        # Only {company_name} and {candidate_first_name} are substituted —
        # via plain str.replace, so ANY other content (stray braces,
        # {unknown_fields}, {0}) passes through byte-for-byte and can never
        # raise KeyError/IndexError -> no 500 from a pasted template.
        tpl = _load_template_config(db) or {}
        raw_subject = tpl.get("subject_template")
        if raw_subject:
            subject = (
                raw_subject
                .replace("{company_name}", company_name or "Onboard Chaser AI")
                .replace("{candidate_first_name}", candidate_name.split(" ")[0])
            )
        else:
            subject = f"Complete your onboarding for {company_name or 'Onboard Chaser AI'}"
        resp = _send_resend(to=candidate_email, subject=subject, html=html, text=text)
        # Resend returns a dict‑like object; we record what we can.
        result.update(
            status=InvitationEmailStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # broad – catches invalid recipient, rate‑limit, etc.
        result.update(
            status=InvitationEmailStatus.FAILED,
            last_error=str(exc),
        )

    return result