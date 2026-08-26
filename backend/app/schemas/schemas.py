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
