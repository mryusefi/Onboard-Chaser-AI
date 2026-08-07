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

    candidate = relationship("Candidate", back_populates="onboarding")
    documents = relationship("Document", back_populates="onboarding")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    onboarding_id = Column(UUID(as_uuid=True), ForeignKey("onboardings.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    required = Column(Boolean, default=True)
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.PENDING)
    file_key = Column(String(512), nullable=True)
    file_name = Column(String(255), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    onboarding = relationship("Onboarding", back_populates="documents")
