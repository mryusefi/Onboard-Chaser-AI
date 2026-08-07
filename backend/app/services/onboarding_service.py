from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Candidate, Onboarding, OnboardingStatus, Document
from app.core.security import create_magic_token, validate_magic_token
from app.core.config import settings


def create_onboarding(
    db: Session, candidate_id: UUID, document_names: list[str] = None
) -> Onboarding:
    """Create an onboarding record for a candidate with required documents."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise ValueError("Candidate not found")

    existing = db.query(Onboarding).filter(
        Onboarding.candidate_id == candidate_id
    ).first()
    if existing:
        raise ValueError("Onboarding already exists for this candidate")

    onboarding = Onboarding(
        candidate_id=candidate_id,
        status=OnboardingStatus.PENDING,
    )
    db.add(onboarding)
    db.flush()

    if document_names is None:
        document_names = [
            "Government ID",
            "Proof of Address",
            "Tax Form (W-4)",
            "Signed Offer Letter",
        ]

    for doc_name in document_names:
        doc = Document(
            onboarding_id=onboarding.id,
            name=doc_name,
            required=True,
        )
        db.add(doc)

    db.commit()
    db.refresh(onboarding)
    return onboarding


def generate_magic_link(db: Session, onboarding_id: UUID) -> dict:
    """Generate a secure magic link token for a candidate to access their portal."""
    onboarding = db.query(Onboarding).filter(
        Onboarding.id == onboarding_id
    ).first()
    if not onboarding:
        raise ValueError("Onboarding not found")

    candidate = db.query(Candidate).filter(
        Candidate.id == onboarding.candidate_id
    ).first()

    token = create_magic_token(str(candidate.id), candidate.email)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.MAGIC_TOKEN_EXPIRE_HOURS
    )

    onboarding.magic_token = token
    onboarding.token_expires_at = expires_at
    db.commit()

    portal_url = f"{settings.FRONTEND_URL}/onboard/{token}"
    return {"magic_link": portal_url, "expires_at": expires_at}


def validate_candidate_access(db: Session, token: str) -> dict:
    """Validate a magic link token and return onboarding portal data."""
    payload = validate_magic_token(token)
    if not payload:
        raise ValueError("Invalid or expired token")

    candidate_id = payload.get("sub")
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id
    ).first()
    if not candidate:
        raise ValueError("Candidate not found")

    onboarding = db.query(Onboarding).filter(
        Onboarding.candidate_id == candidate_id
    ).first()
    if not onboarding:
        raise ValueError("No onboarding process found")

    if onboarding.token_expires_at:
        if datetime.now(timezone.utc) > onboarding.token_expires_at:
            raise ValueError("Token has expired")

    if not onboarding.is_token_used:
        onboarding.is_token_used = True
        onboarding.started_at = datetime.now(timezone.utc)
        onboarding.status = OnboardingStatus.IN_PROGRESS
        db.commit()

    documents = [
        {
            "id": str(doc.id),
            "name": doc.name,
            "description": doc.description,
            "required": doc.required,
            "status": doc.status.value,
        }
        for doc in onboarding.documents
    ]

    return {
        "onboarding_id": str(onboarding.id),
        "candidate_name": candidate.full_name,
        "candidate_email": candidate.email,
        "status": onboarding.status.value,
        "documents": documents,
    }
