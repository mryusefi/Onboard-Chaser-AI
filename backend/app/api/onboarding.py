import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.schemas.schemas import (
    OnboardingResponse,
    OnboardingPortalResponse,
    OnboardingCreate,
    FullOnboardingCreate,
    CandidateOnboardingResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    DocumentResponse,
    ReminderLogResponse,
    ReminderSendResponse,
)
from app.services.onboarding_service import (
    create_onboarding_for_candidate,
    create_full_onboarding,
    generate_magic_link,
    validate_candidate_access,
    compute_completion_percentage,
    update_document_status,
)
from app.services.email_service import send_invitation as send_email, is_email_configured
from app.services.reminder_service import send_reminder, REMINDER_TYPE_MIDWAY
from app.models.models import Onboarding, ReminderLog, InvitationEmailStatus as IES
from app.services.document_service import (
    upload_file_to_storage,
    get_document_for_upload,
)
from app.services import storage

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/magic-link", response_model=MagicLinkResponse)
def request_magic_link(body: MagicLinkRequest, db: Session = Depends(get_db)):
    """Generate a secure magic link for candidate portal access."""
    try:
        result = generate_magic_link(db, UUID(str(body.candidate_id)))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/portal/{token}", response_model=OnboardingPortalResponse)
def access_portal(token: str, db: Session = Depends(get_db)):
    """Validate magic token and return onboarding portal data."""
    try:
        data = validate_candidate_access(db, token)
        return data
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/create-full", response_model=CandidateOnboardingResponse)
def create_full_onboarding_endpoint(
    body: FullOnboardingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Convenience endpoint (US06): create candidate + onboarding (+ seeded
    documents) in one request. Requires HR authentication.
    """
    from app.models.models import Candidate as CandidateModel

    try:
        candidate, onboarding, documents = create_full_onboarding(db, body)
    except ValueError as e:
        msg = str(e)
        if msg == "duplicate_email":
            raise HTTPException(status_code=409, detail="Candidate already exists")
        if msg == "onboarding_exists":
            raise HTTPException(
                status_code=409, detail="Onboarding already exists for this candidate"
            )
        if msg == "no_hr_user":
            raise HTTPException(status_code=400, detail="No HR user exists yet. Register first.")
        raise HTTPException(status_code=400, detail=msg)

    # Re-query for fresh ORM state to satisfy from_attributes serialization.
    cand = db.query(CandidateModel).filter(CandidateModel.id == candidate.id).first()
    docs = [
        DocumentResponse.model_validate(d) for d in documents
    ]
    return CandidateOnboardingResponse(
        candidate=cand,
        onboarding=onboarding,
        documents=docs,
    )



@router.post("/{candidate_id}", response_model=OnboardingResponse)
def start_onboarding(
    candidate_id: str,
    body: OnboardingCreate | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create an onboarding process for an existing candidate (US06).

    Requires HR authentication. Optional JSON body may carry a custom
    required_documents list; when omitted the 4 default documents are seeded.
    """
    try:
        cid = UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    custom_docs = (
        [d.model_dump() for d in body.required_documents]
        if body and body.required_documents
        else None
    )
    try:
        onboarding, _ = create_onboarding_for_candidate(db, cid, custom_docs)
        return onboarding
    except ValueError as e:
        msg = str(e)
        if msg == "candidate_not_found":
            raise HTTPException(status_code=404, detail="Candidate not found")
        if msg == "onboarding_exists":
            raise HTTPException(
                status_code=409, detail="Onboarding already exists for this candidate"
            )
        raise HTTPException(status_code=400, detail=msg)


@router.get("/document/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get a single document requirement by ID."""
    try:
        return get_document_for_upload(db, document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/document/{document_id}/status")
def change_document_status(
    document_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Update a document's status (US05: Pending/Uploaded/Completed/Missing)."""
    new_status = payload.get("status", "")
    try:
        result = update_document_status(db, document_id, new_status)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/progress/{onboarding_id}")
def get_onboarding_progress(onboarding_id: str, db: Session = Depends(get_db)):
    """Return document completion percentage for an onboarding (US05)."""
    from uuid import UUID as _UUID

    try:
        oid = _UUID(onboarding_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid onboarding ID")
    try:
        progress = compute_completion_percentage(db, onboarding_id=oid)
        return progress
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/document/{document_id}/upload", response_model=DocumentResponse)
async def upload_document(
    document_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a file for a specific document requirement."""
    try:
        contents = await file.read()
        result = upload_file_to_storage(db, document_id, contents, file.filename)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/storage/status")
def storage_status():
    """Report current document storage configuration (US04)."""
    return {
        "r2_configured": storage.is_r2_configured(),
        "encryption_enabled": True,
        "encryption_algorithm": "AES-256-Fernet",
        "storage_backend": "cloudflare_r2" if storage.is_r2_configured() else "local_filesystem",
        "bucket": settings.R2_BUCKET_NAME or None,
        "structure": "onboardings/{onboarding_id}/{document_id}.{ext}",
    }


# ────────────────────────────────────────────────────────────────────────
# US07 — Invitation e‑mail endpoints
# ────────────────────────────────────────────────────────────────────────
@router.post("/{onboarding_id}/send-invitation")
def send_invitation_endpoint(
    onboarding_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Send (or re‑send) the candidate invitation e‑mail (US07).

    Returns the delivery status, the portal URL, and the expiry. The status
    can be `not_sent` (no Resend key), `sent` (provider accepted), `failed`
    (provider error – see `last_error`), or `delivered` / `bounced` (only
    if a Resend webhook is configured – see README).
    """
    try:
        oid = UUID(onboarding_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid onboarding ID")

    onboarding = db.query(Onboarding).filter(Onboarding.id == oid).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    candidate = onboarding.candidate
    try:
        result = send_email(
            candidate_name=candidate.full_name,
            company_name=settings.APP_NAME,
            position=candidate.position,
            candidate_email=candidate.email,
            onboarding_id=onboarding.id,
            db=db,
        )
    except ValueError as e:
        if str(e) == "onboarding_not_found":
            raise HTTPException(status_code=404, detail="Onboarding not found")
        raise HTTPException(status_code=400, detail=str(e))

    # Persist tracking fields
    onboarding.invitation_email_status = result["status"]
    onboarding.invitation_sent_at = result.get("sent_at")
    onboarding.invitation_last_error = result.get("last_error")
    db.commit()

    return {
        "onboarding_id": str(onboarding.id),
        "candidate_email": candidate.email,
        "status": onboarding.invitation_email_status.value,
        "sent_at": onboarding.invitation_sent_at.isoformat() if onboarding.invitation_sent_at else None,
        "last_error": onboarding.invitation_last_error,
        "portal_url": result["portal_url"],
        "expiry_hours": result["expiry_hours"],
        "email_configured": is_email_configured(),
    }


@router.get("/{onboarding_id}/invitation-status")
def invitation_status_endpoint(
    onboarding_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return current invitation tracking fields without resending (US07)."""
    try:
        oid = UUID(onboarding_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid onboarding ID")

    onboarding = db.query(Onboarding).filter(Onboarding.id == oid).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    return {
        "onboarding_id": str(onboarding.id),
        "candidate_email": onboarding.candidate.email,
        "status": onboarding.invitation_email_status.value,
        "sent_at": onboarding.invitation_sent_at.isoformat() if onboarding.invitation_sent_at else None,
        "last_error": onboarding.invitation_last_error,
    }


# ────────────────────────────────────────────────────────────────────────
# US08 — Automated reminder endpoints
# ────────────────────────────────────────────────────────────────────────
def _get_onboarding_or_404(db: Session, onboarding_id: str) -> Onboarding:
    """Shared lookup: 400 on bad UUID, 404 on unknown onboarding."""
    try:
        oid = UUID(onboarding_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid onboarding ID")
    onboarding = db.query(Onboarding).filter(Onboarding.id == oid).first()
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding not found")
    return onboarding


@router.get("/{onboarding_id}/reminders", response_model=list[ReminderLogResponse])
def get_reminder_history(
    onboarding_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Reminder history for an onboarding (US08) — every attempt (sent, failed,
    skipped) as a ReminderLog entry, oldest first. HR-authenticated.
    """
    onboarding = _get_onboarding_or_404(db, onboarding_id)
    logs = (
        db.query(ReminderLog)
        .filter(ReminderLog.onboarding_id == onboarding.id)
        .order_by(ReminderLog.sent_at.asc(), ReminderLog.id.asc())
        .all()
    )
    return logs


@router.post("/{onboarding_id}/send-reminder-now", response_model=ReminderSendResponse)
def send_reminder_now(
    onboarding_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Manual reminder trigger (US08) — same send_reminder() logic as the
    scheduled task, logged identically in ReminderLog. `force=True` bypasses
    cooldown/cap for HR override, but the attempt is still audited.
    """
    onboarding = _get_onboarding_or_404(db, onboarding_id)

    log = send_reminder(db, onboarding, REMINDER_TYPE_MIDWAY, force=True)

    return ReminderSendResponse(
        onboarding_id=onboarding.id,
        candidate_email=onboarding.candidate.email,
        status=log.status.value,
        reminder_type=log.reminder_type,
        reason=log.reason,
        sent_at=log.sent_at,
    )
