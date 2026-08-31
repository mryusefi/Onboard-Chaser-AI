from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Candidate
from app.schemas.schemas import CandidateCreate, CandidateResponse

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/", response_model=CandidateResponse)
def create_candidate(
    body: CandidateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a new candidate record (US06). Requires HR authentication.

    Returns 409 when a candidate with the same email already exists.
    """
    from app.services.onboarding_service import create_candidate as _create_candidate

    try:
        return _create_candidate(db, body)
    except ValueError as e:
        if str(e) == "duplicate_email":
            raise HTTPException(status_code=409, detail="Candidate already exists")
        raise HTTPException(status_code=400, detail=str(e))
