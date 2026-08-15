from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import (
    Candidate,
    Onboarding,
    OnboardingStatus,
    Document,
    DocumentStatus,
)
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
        default_docs = [
            {
                "name": "Government ID",
                "instructions": "Upload a clear, full-color photo or scan of your government-issued photo ID (passport, driver's license, or national ID card). All four corners must be visible and text must be legible.",
                "accepted_formats": "PDF, JPG, PNG",
            },
            {
                "name": "Proof of Address",
                "instructions": "Upload a recent utility bill, bank statement, or official letter showing your current residential address. The document must be dated within the last 3 months.",
                "accepted_formats": "PDF, JPG, PNG",
            },
            {
                "name": "Tax Form (W-4)",
                "instructions": "Download and complete the IRS W-4 form. Ensure all fields are filled, sign and date the form before uploading. If you are unsure about any section, contact HR before submitting.",
                "accepted_formats": "PDF",
            },
            {
                "name": "Signed Offer Letter",
                "instructions": "Upload the signed copy of your employment offer letter. Both your signature and the employer's signature must be present. Scan or photograph the entire document.",
                "accepted_formats": "PDF, JPG, PNG",
            },
        ]
    else:
        default_docs = [{"name": n, "instructions": None, "accepted_formats": "PDF, JPG, PNG"} for n in document_names]

    for doc_data in default_docs:
        doc = Document(
            onboarding_id=onboarding.id,
            name=doc_data["name"],
            instructions=doc_data.get("instructions"),
            accepted_formats=doc_data.get("accepted_formats"),
            required=True,
        )
        db.add(doc)

    db.commit()
    db.refresh(onboarding)
    return onboarding


def generate_magic_link(db: Session, candidate_id: UUID) -> dict:
    """Generate a secure magic link token for a candidate to access their portal."""
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id
    ).first()
    if not candidate:
        raise ValueError("Candidate not found")

    onboarding = db.query(Onboarding).filter(
        Onboarding.candidate_id == candidate_id
    ).first()
    if not onboarding:
        raise ValueError("Onboarding not found for this candidate")

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

    candidate_id = UUID(payload.get("sub"))
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
        now = datetime.now(timezone.utc)
        expires = onboarding.token_expires_at
        # Normalize to timezone-aware for comparison (SQLite returns naive)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
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
            "instructions": doc.instructions,
            "accepted_formats": doc.accepted_formats,
            "required": doc.required,
            "status": doc.status.value,
        }
        for doc in onboarding.documents
    ]

    progress = compute_completion_percentage(db, onboarding)

    return {
        "onboarding_id": str(onboarding.id),
        "candidate_name": candidate.full_name,
        "candidate_email": candidate.email,
        "status": onboarding.status.value,
        "documents": documents,
        "completion_percentage": progress["completion_percentage"],
        "completed_documents": progress["completed_documents"],
        "total_documents": progress["total_documents"],
    }


def compute_completion_percentage(
    db: Session, onboarding: Onboarding = None, onboarding_id=None
) -> dict:
    """
    Compute onboarding document completion stats (US05).

    A document counts as completed when its status is 'uploaded' or 'completed'.
    Required documents are the baseline; optional documents do not penalize.
    """
    if onboarding is None:
        if onboarding_id is None:
            raise ValueError("onboarding or onboarding_id is required")
        onboarding = db.query(Onboarding).filter(
            Onboarding.id == onboarding_id
        ).first()
        if not onboarding:
            raise ValueError("Onboarding not found")

    docs = db.query(Document).filter(Document.onboarding_id == onboarding.id).all()
    total = len(docs)
    done = sum(
        1 for d in docs if d.status in (DocumentStatus.UPLOADED, DocumentStatus.COMPLETED)
    )
    pending = sum(1 for d in docs if d.status == DocumentStatus.PENDING)
    missing = sum(1 for d in docs if d.status == DocumentStatus.MISSING)
    percent = round((done / total) * 100) if total else 0

    # Auto-complete onboarding when all required documents are done
    if total and done == total and onboarding.status != OnboardingStatus.COMPLETED:
        onboarding.status = OnboardingStatus.COMPLETED
        onboarding.completed_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "completion_percentage": percent,
        "completed_documents": done,
        "pending_documents": pending,
        "missing_documents": missing,
        "total_documents": total,
    }


def update_document_status(
    db: Session, document_id: str, new_status: str
) -> dict:
    """
    Update a document's status (US05).

    Allowed transitions:
      pending  -> uploaded | missing | completed
      uploaded -> completed | missing
      completed -> uploaded
      missing  -> pending | uploaded
    """
    try:
        doc_id = UUID(document_id)
    except (ValueError, AttributeError):
        raise ValueError("Invalid document ID")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("Document not found")

    try:
        target = DocumentStatus(new_status.lower())
    except ValueError:
        raise ValueError(
            f"Invalid status '{new_status}'. Allowed: pending, uploaded, completed, missing"
        )

    doc.status = target
    if target == DocumentStatus.COMPLETED:
        doc.uploaded_at = doc.uploaded_at or datetime.now(timezone.utc)
    db.commit()

    # Recompute completion for the parent onboarding
    onboarding = db.query(Onboarding).filter(
        Onboarding.id == doc.onboarding_id
    ).first()
    progress = compute_completion_percentage(db, onboarding)

    return {
        "id": str(doc.id),
        "name": doc.name,
        "status": doc.status.value,
        "completion_percentage": progress["completion_percentage"],
        "completed_documents": progress["completed_documents"],
        "total_documents": progress["total_documents"],
    }
