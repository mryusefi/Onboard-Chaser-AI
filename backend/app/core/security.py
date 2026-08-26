from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

# Used to extract the Bearer token from HR-facing requests.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_magic_token(candidate_id: str, email: str) -> str:
    """Create a time-limited token for candidate portal access."""
    to_encode = {
        "sub": candidate_id,
        "email": email,
        "type": "magic",
        "jti": str(uuid.uuid4()),
    }
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.MAGIC_TOKEN_EXPIRE_HOURS
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def validate_magic_token(token: str) -> Optional[dict]:
    """Validate a magic link token and return payload or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "magic":
            return None
        return payload
    except JWTError:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> "User":
    """
    HR authentication dependency (US06).

    Extracts the Bearer token, decodes it and loads the corresponding User.
    Raises 401 when the token is missing/invalid or the user no longer exists.
    """
    credentials_exception = HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    from app.models.models import User

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise credentials_exception
    return user
