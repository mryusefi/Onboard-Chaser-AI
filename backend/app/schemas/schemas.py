from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr


# --- User Schemas ---
class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_hr: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Candidate Schemas ---
class CandidateCreate(BaseModel):
    email: str
    full_name: str
    phone: Optional[str] = None
    position: Optional[str] = None


class CandidateResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone: Optional[str]
    position: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Onboarding Schemas ---
class OnboardingResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    status: str
    is_token_used: bool
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class OnboardingPortalResponse(BaseModel):
    onboarding_id: UUID
    candidate_name: str
    candidate_email: str
    status: str
    documents: List[dict]
    completion_percentage: int = 0
    completed_documents: int = 0
    total_documents: int = 0


# --- Document Schemas ---
class DocumentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    instructions: Optional[str] = None
    accepted_formats: Optional[str] = None
    required: bool
    status: str
    file_name: Optional[str]
    file_key: Optional[str] = None
    file_size: Optional[str] = None
    file_mime_type: Optional[str] = None
    encryption_algorithm: Optional[str] = None
    file_url: Optional[str] = None
    uploaded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Magic Link ---
class MagicLinkRequest(BaseModel):
    candidate_id: UUID


class MagicLinkResponse(BaseModel):
    magic_link: str
    expires_at: datetime


# --- US06: HR onboarding creation ---
class RequiredDocumentCreate(BaseModel):
    """A single custom required document to seed into a new onboarding."""
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    accepted_formats: Optional[str] = "PDF, JPG, PNG"
    required: bool = True


class OnboardingCreate(BaseModel):
    """
    Payload for creating an onboarding process for an existing candidate.

    required_documents can be omitted -> the 4 default documents are seeded.
    When provided, these custom documents REPLACE the defaults (documented
    decision in onboarding_service.create_onboarding_for_candidate).
    """
    candidate_id: UUID
    required_documents: Optional[List[RequiredDocumentCreate]] = None


class CandidateOnboardingResponse(BaseModel):
    """
    Combined response for the convenience endpoint: candidate + onboarding +
    the list of seeded documents.
    """
    candidate: CandidateResponse
    onboarding: OnboardingResponse
    documents: List[DocumentResponse]


class FullOnboardingCreate(BaseModel):
    """
    Payload for the combined convenience endpoint (US06): creates the
    candidate and their onboarding in a single request.
    """
    candidate: CandidateCreate
    required_documents: Optional[List[RequiredDocumentCreate]] = None


# --- US08: Reminder history ---
class ReminderLogResponse(BaseModel):
    """One reminder attempt against an onboarding (audit trail entry)."""
    id: UUID
    onboarding_id: UUID
    status: str
    reminder_type: str
    reason: Optional[str] = None
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReminderSendResponse(BaseModel):
    """Result of a manual send-reminder-now trigger (US08)."""
    onboarding_id: UUID
    candidate_email: str
    status: str
    reminder_type: str
    reason: Optional[str] = None
    sent_at: Optional[datetime] = None


# --- US09: Reminder configuration (singleton, HR-managed) ---
class ReminderConfigResponse(BaseModel):
    """The global reminder configuration row (US09)."""
    reminder_frequency_hours: int
    first_reminder_after_hours: int
    final_reminder_before_expiry_hours: int
    max_reminders_per_onboarding: int
    is_enabled: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReminderConfigUpdate(BaseModel):
    """
    Payload for PUT /api/v1/settings/reminders (US09).

    Field-level range checks are enforced in reminder_service.
    apply_reminder_config (single source of truth) so the API and any future
    callers share the exact same rules; validation errors surface as 422.
    """
    reminder_frequency_hours: Optional[int] = None
    first_reminder_after_hours: Optional[int] = None
    final_reminder_before_expiry_hours: Optional[int] = None
    max_reminders_per_onboarding: Optional[int] = None
    is_enabled: Optional[bool] = None


# --- US10: HR dashboard list ---
class CandidateBrief(BaseModel):
    """Candidate fields shown in the dashboard list (US10)."""
    full_name: str
    email: str
    position: Optional[str] = None


class OnboardingListItemResponse(BaseModel):
    """
    One row of the HR dashboard list (US10).

    needs_attention is derived by the documented rule in
    onboarding_service.list_onboardings (expired link / never invited /
    zero progress > 24h / reminder failed or cap-reached skip).
    """
    onboarding_id: UUID
    candidate: CandidateBrief
    status: str
    completion_percentage: int
    completed_documents: int
    total_documents: int
    invitation_email_status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    needs_attention: bool


class OnboardingListResponse(BaseModel):
    """Paginated onboarding list with metadata (US10)."""
    items: List[OnboardingListItemResponse]
    total: int
    page: int
    page_size: int
