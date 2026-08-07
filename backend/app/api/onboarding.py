from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import (
    OnboardingResponse,
    OnboardingPortalResponse,
    MagicLinkRequest,
    MagicLinkResponse,
)
from app.services.onboarding_service import (
    create_onboarding,
    generate_magic_link,
    validate_candidate_access,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/{candidate_id}", response_model=OnboardingResponse)
def start_onboarding(candidate_id: str, db: Session = Depends(get_db)):
    """Create an onboarding process for a candidate."""
    from uuid import UUID

    try:
        cid = UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID")

    try:
        onboarding = create_onboarding(db, cid)
        return onboarding
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/magic-link", response_model=MagicLinkResponse)
def request_magic_link(body: MagicLinkRequest, db: Session = Depends(get_db)):
    """Generate a secure magic link for candidate portal access."""
    from uuid import UUID

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
