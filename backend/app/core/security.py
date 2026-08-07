from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


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
