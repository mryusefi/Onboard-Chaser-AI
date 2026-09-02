import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
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
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.PENDING)
    file_key = Column(String(512), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size = Column(String(32), nullable=True)
    file_mime_type = Column(String(128), nullable=True)
    encryption_algorithm = Column(String(64), nullable=True)
    file_url = Column(String(1024), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    onboarding = relationship("Onboarding", back_populates="documents")


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
