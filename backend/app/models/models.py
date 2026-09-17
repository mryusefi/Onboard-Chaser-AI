import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class OnboardingStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    COMPLETED = "completed"
    MISSING = "missing"


class DocumentType(str, enum.Enum):
    """
    Maintenance pass Part C — what KIND of artifact a required document is.

    Categorization only: the upload validation still runs off
    ``accepted_formats`` (extension whitelist in document_service), so the
    type drives the default formats offered at creation time, not the
    security rules.

    NOTE (deferred by design): a `text_input` type (free-text answer instead
    of a file) is NOT implemented here — it needs a portal text-answer UI,
    storage semantics for non-file answers, and verification handling for
    text; that's a proper follow-up story rather than half-built in a
    maintenance pass.
    """
    IMAGE = "image"                # photos/scans -> JPG, PNG, GIF
    PDF_DOCUMENT = "pdf_document"  # signed forms -> PDF
    FILE = "file"                  # anything allowed -> PDF, JPG, PNG, GIF


class DocumentVerificationStatus(str, enum.Enum):
    """
    US11 — HR-driven manual verification of an uploaded document.

    This is MANUAL verification only (an HR coordinator eyeballs the file via
    the preview/download access URL and marks it verified/rejected). AI-assisted
    document verification is US12 and remains out of scope for this MVP,
    unchanged from the original project scope statement.
    """
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class InvitationEmailStatus(str, enum.Enum):
    """Delivery tracking for the candidate invitation email (US07)."""
    NOT_SENT = "not_sent"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    BOUNCED = "bounced"


class ReminderStatus(str, enum.Enum):
    """Outcome of one reminder attempt (US08 audit trail)."""
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReminderConfig(Base):
    """
    US09 — Reminder configuration.

    SCOPE DECISION (MVP): a SINGLE GLOBAL config row (singleton, id=1), not
    per-onboarding overrides. Rationale: the MVP needs one HR-tunable policy;
    per-onboarding overrides add UI + precedence rules with no MVP use case.
    The row is auto-created with built-in defaults on first read
    (see reminder_service.get_reminder_config) — no seed script needed.

    Field mapping vs. the US08 env-var fallbacks (app/core/config.py):
      reminder_frequency_hours          <- REMINDER_COOLDOWN_HOURS (min
                                           interval between reminder attempts)
      first_reminder_after_hours        <- new: no reminder before this many
                                           hours since the invitation anchor
      final_reminder_before_expiry_hours<- REMINDER_EXPIRY_WINDOW_HOURS
      max_reminders_per_onboarding      <- REMINDER_MAX_COUNT
      is_enabled                        <- REMINDER_ENABLED (both must be true;
                                           env var stays as a deploy-level kill
                                           switch, the row is HR's runtime one)
    REMINDER_SCAN_INTERVAL_MINUTES (celery-beat tick) and
    REMINDER_MIDWAY_PERCENT (midway fraction) stay env-var driven: the beat
    schedule is read once at worker startup, and a midway percentage is a
    deployment policy, not an HR daily knob.
    """
    __tablename__ = "reminder_configs"

    id = Column(Integer, primary_key=True, default=1)  # singleton row (id=1)
    reminder_frequency_hours = Column(Integer, nullable=False, default=24)
    first_reminder_after_hours = Column(Integer, nullable=False, default=24)
    final_reminder_before_expiry_hours = Column(Integer, nullable=False, default=24)
    max_reminders_per_onboarding = Column(Integer, nullable=False, default=3)
    is_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class EmailTemplateConfig(Base):
    """
    Maintenance pass Item 1b — HR-editable invitation email COPY.

    Same singleton pattern as ReminderConfig (id=1, auto-created on first
    read, fallback to the hardcoded template when the row is absent).

    SECURITY/SCOPE: this stores only the SAFE-TO-EDIT copy (subject line,
    greeting/body intro, closing + optional extra instructions). The
    functional parts of the email — the portal link, the document list, the
    expiry notice — are always injected programmatically by email_service.py
    and can NOT be edited or removed here. The RESEND_API_KEY itself is a
    server environment variable and is deliberately NOT configurable from
    the UI or stored in the database (same rule as R2 credentials).
    """
    __tablename__ = "email_template_configs"

    id = Column(Integer, primary_key=True, default=1)  # singleton row (id=1)
    # {company_name} and {candidate_first_name} placeholders are substituted
    # by email_service at render time; None/empty subject falls back to the
    # built-in default subject.
    subject_template = Column(String(200), nullable=True)
    body_intro = Column(Text, nullable=True)       # greeting + intro paragraph
    body_closing = Column(Text, nullable=True)     # closing lines before the link CTA
    extra_instructions = Column(Text, nullable=True)  # HR's extra bullet points
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_hr = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    position = Column(String(255), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    onboarding = relationship("Onboarding", back_populates="candidate", uselist=False)


class Onboarding(Base):
    __tablename__ = "onboardings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), unique=True, nullable=False)
    status = Column(SAEnum(OnboardingStatus), default=OnboardingStatus.PENDING)
    magic_token = Column(Text, nullable=True, unique=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_token_used = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # US07: invitation email delivery tracking
    invitation_sent_at = Column(DateTime(timezone=True), nullable=True)
    invitation_email_status = Column(
        SAEnum(InvitationEmailStatus), default=InvitationEmailStatus.NOT_SENT
    )
    invitation_last_error = Column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="onboarding")
    documents = relationship("Document", back_populates="onboarding")
    reminder_logs = relationship(
        "ReminderLog", back_populates="onboarding", order_by="ReminderLog.sent_at"
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    onboarding_id = Column(UUID(as_uuid=True), ForeignKey("onboardings.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    required = Column(Boolean, default=True)
    accepted_formats = Column(String(255), nullable=True)
    # Maintenance pass Part C: categorization of what the document IS
    # (image / pdf_document / file). Upload validation still keys off
    # accepted_formats; nullable so pre-existing rows are unaffected.
    document_type = Column(SAEnum(DocumentType), nullable=True)
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.PENDING)
    file_key = Column(String(512), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size = Column(String(32), nullable=True)
    file_mime_type = Column(String(128), nullable=True)
    encryption_algorithm = Column(String(64), nullable=True)
    file_url = Column(String(1024), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # US11 — manual HR verification (see DocumentVerificationStatus docstring:
    # manual only; AI verification is US12, out of MVP scope).
    verification_status = Column(
        SAEnum(DocumentVerificationStatus), default=DocumentVerificationStatus.UNVERIFIED
    )
    verification_note = Column(Text, nullable=True)  # e.g. rejection reason
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    onboarding = relationship("Onboarding", back_populates="documents")
    verifier = relationship("User")


class ReminderLog(Base):
    """
    Persistent audit trail for automated reminder attempts (US08).

    One row is written for EVERY reminder attempt against an onboarding —
    sent, failed (provider error) or skipped (cooldown/cap/disabled) — so HR
    can see exactly what the reminder system did and when (US08 requirement:
    "log reminder history").
    """
    __tablename__ = "reminder_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    onboarding_id = Column(
        UUID(as_uuid=True), ForeignKey("onboardings.id"), nullable=False, index=True
    )
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(SAEnum(ReminderStatus), nullable=False)
    # reminder_type classifies WHY the reminder fired: "midway" (50% of token
    # lifetime elapsed) or "expiry_warning" (within the pre-expiry window).
    reminder_type = Column(String(50), nullable=False)
    # Human-readable reason: skip motive (cooldown/cap/disabled) or the
    # provider error message when status == failed.
    reason = Column(Text, nullable=True)

    onboarding = relationship("Onboarding", back_populates="reminder_logs")
