from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import User, Candidate, Onboarding, Document
from app.schemas.schemas import CandidateCreate, CandidateResponse

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/", response_model=CandidateResponse)
def create_candidate(body: CandidateCreate, db: Session = Depends(get_db)):
    """Create a new candidate record."""
    from app.core.security import create_access_token

    existing = db.query(Candidate).filter(Candidate.email == body.email).first()
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Candidate already exists")

    # For now, use a placeholder creator. In production, extract from JWT.
    placeholder_hr = db.query(User).first()
    if not placeholder_hr:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No HR user exists yet. Register first.")

    candidate = Candidate(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        position=body.position,
        created_by=placeholder_hr.id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate
