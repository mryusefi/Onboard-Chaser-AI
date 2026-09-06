"""US11 — HR document access (short-lived URLs) + manual verification endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import (
    DocumentAccessUrlResponse,
    DocumentVerificationResponse,
    DocumentVerificationUpdate,
)
from app.services.document_service import (
    ACCESS_URL_EXPIRY_SECONDS,
    get_document_access_url,
    serve_document_bytes,
    update_verification,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _handle_value_error(exc: ValueError):
    """Map service ValueErrors to HTTP codes (US11)."""
    msg = str(exc)
    if msg in ("document_not_found", "no_file_uploaded", "file_missing_on_disk"):
        raise HTTPException(status_code=404, detail=msg)
    if msg == "invalid_or_expired_token":
        raise HTTPException(status_code=403, detail=msg)
    if msg.startswith("invalid_verification_status"):
        raise HTTPException(status_code=422, detail=msg)
    if msg.startswith("no_file_uploaded:"):
        raise HTTPException(status_code=409, detail=msg)
    raise HTTPException(status_code=400, detail=msg)


@router.get("/{document_id}/access-url", response_model=DocumentAccessUrlResponse)
def get_access_url(
    document_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Short-lived signed URL for preview/download (US11, HR auth).

    Returns a URL valid for {ACCESS_URL_EXPIRY_SECONDS}s (10 min): an R2
    presigned GET when R2 is configured, otherwise a signed local API URL.
    The JSON response NEVER contains decrypted file bytes. 404 when the
    document doesn't exist or has no uploaded file yet.
    """
    try:
        return get_document_access_url(db, document_id)
    except ValueError as exc:
        _handle_value_error(exc)


@router.patch("/{document_id}/verification", response_model=DocumentVerificationResponse)
def patch_verification(
    document_id: str,
    body: DocumentVerificationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Manual HR verification (US11, HR auth).

    Accepts {verification_status: unverified|verified|rejected,
    verification_note?}. Records verified_by (authenticated HR user) and
    verified_at=now. 409 when the document has no uploaded file (nothing to
    verify); 422 for invalid enum values.

    NOTE: manual HR verification only — AI verification is US12 (out of MVP scope).
    """
    try:
        return update_verification(
            db,
            document_id,
            body.verification_status,
            body.verification_note,
            hr_user_id=current_user.id,
        )
    except ValueError as exc:
        _handle_value_error(exc)


@router.get("/{document_id}/file")
def stream_document_file(
    document_id: str,
    token: str,
    db: Session = Depends(get_db),
):
    """
    Local-fallback file streaming (US11) — the local equivalent of an R2
    presigned GET. Access is granted by the SHORT-LIVED signed token in the
    query string (same HMAC scheme/expiry semantics as R2 presigned URLs),
    NOT by HR JWT: the browser hits this URL directly for inline preview
    (<iframe>/<img>) or download. Token is validated (signature + expiry +
    document match) before bytes are decrypted on the fly.

    NOTE: intentionally NOT behind get_current_user — possession of a valid,
    unexpired signed token IS the authorization (exactly like R2 presigned
    URLs). The token is only ever handed out through the HR-authenticated
    access-url endpoint above.
    """
    if document_id != token_claims_subject(token):
        # Token must be scoped to THIS document (no cross-document reuse).
        from app.services.document_service import serve_document_bytes
        try:
            serve_document_bytes(db, token)  # full validation for error parity
        except ValueError as exc:
            _handle_value_error(exc)
        raise HTTPException(status_code=403, detail="token does not match document")

    from app.services.document_service import serve_document_bytes

    try:
        data, mime, file_name = serve_document_bytes(db, token)
    except ValueError as exc:
        _handle_value_error(exc)

    headers = {}
    if mime.startswith("image/") or mime == "application/pdf":
        headers["Content-Disposition"] = f'inline; filename="{file_name}"'
    else:
        headers["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return Response(content=data, media_type=mime, headers=headers)


def token_claims_subject(token: str) -> str | None:
    """Decode the access token's `sub` claim without DB access (US11)."""
    from jose import jwt, JWTError

    from app.core.config import settings
    from app.services.storage import LOCAL_ACCESS_TOKEN_TYPE

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("type") != LOCAL_ACCESS_TOKEN_TYPE:
        return None
    return payload.get("sub")
