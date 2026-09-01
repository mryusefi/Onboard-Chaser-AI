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

    <p>Hello {{ candidate_name }},</p>

    <p>You have been invited to complete onboarding for <strong>{{ company_name }}</strong>.
    Your position is <strong>{{ position }}</strong>.</p>

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

    <p style="margin-top:24px">
      If you have any questions, reply to this email or contact our HR team.
    </p>
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
) -> str:
    """Render the invitation e-mail HTML (and plain-text fallback below)."""
    return _env.from_string(EMAIL_TEMPLATE).render(
        candidate_name=candidate_name,
        company_name=company_name or "Onboard Chaser AI",
        position=position or "",
        portal_url=portal_url,
        expiry_hours=expiry_hours,
        docs=docs,
    )


def render_plain_text(
    candidate_name: str,
    company_name: str,
    position: Optional[str],
    portal_url: str,
    expiry_hours: int,
    docs: list[dict],
) -> str:
    """Very small plain-text fallback so clients that reject HTML still work."""
    lines = [
        f"Hello {candidate_name},",
        f"You have been invited to complete onboarding for {company_name or 'Onboard Chaser AI'}.",
        f"Your position is {position or ''}.",
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
    lines += [
        "",
        f"If you have any questions, reply to this email or contact our HR team.",
        f"Portal URL (copy & share): {portal_url}",
    ]
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────
# 2️⃣ Resend SDK wrapper (fallback when RESEND_API_KEY is absent)
# ────────────────────────────────────────────────────────────────────────
try:
    import resend  # type: ignore
    _resend_configured = bool(os.getenv("RESEND_API_KEY"))
except Exception:  # pragma: no cover
    _resend_configured = False


def is_email_configured() -> bool:
    """True only when RESEND_API_KEY is set (mirrors the R2 pattern in storage.py)."""
    return _resend_configured


def _send_resend(to: str, subject: str, html: str, text: str) -> dict:
    """Blocking call to Resend SDK; raises on provider error."""
    if not _resend_configured:
        raise RuntimeError("RESEND_API_KEY not configured – send_email fell through")
    msg = resend.send(
        from_email=settings.EMAIL_FROM,
        to=to,
        subject=subject,
        html=html,
        text=text,
    )
    return msg  # dict with .id, .status, .tracking_domain, etc.


# ────────────────────────────────────────────────────────────────────────
# 3️⃣ Public API used by the FastAPI route
# ────────────────────────────────────────────────────────────────────────
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
    from app.models.models import Onboarding, Document, InvitationEmailStatus
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
    )
    text = render_plain_text(
        candidate_name=candidate_name,
        company_name=company_name,
        position=position,
        portal_url=portal_url,
        expiry_hours=expiry_hours,
        docs=docs_list,
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
        # Log, but **do not** raise – the API layer will record `not_sent`
        # (the caller can decide to retry later or notify the HR admin).
        import logging
        logging.getLogger(__name__).warning(
            "RESEND_API_KEY not configured – invitation e‑mail not sent (not_sent status)"
        )
        result["status"] = InvitationEmailStatus.NOT_SENT
        result["last_error"] = "RESEND_API_KEY not configured"
        return result

    try:
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