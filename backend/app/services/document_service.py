import os
import mimetypes
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    Document,
    DocumentStatus,
    DocumentVerificationStatus,
    Onboarding,
)
from app.services import storage


# --- File validation constants ---
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif"}
MIMETYPE_BY_EXT = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}


def validate_file(file_content: bytes, filename: str) -> tuple[bool, str]:
    """Validate file size and format. Returns (is_valid, error_message)."""
    if len(file_content) > MAX_FILE_SIZE_BYTES:
        return False, f"File size exceeds {MAX_FILE_SIZE_MB}MB limit"

    if len(file_content) == 0:
        return False, "Uploaded file is empty"

    ext = None
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    if ext and f".{ext}" not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type. Allowed: PDF, JPG, PNG, GIF"

    expected_mime = MIMETYPE_BY_EXT.get(f".{ext}")
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = expected_mime

    if mime_type not in MIMETYPE_BY_EXT.values():
        return False, "Unsupported file type. Allowed: PDF, JPG, PNG, GIF"

    if expected_mime and mime_type != expected_mime:
        return False, f"File extension .{ext} does not match content type {mime_type}"

    return True, ""


def upload_file_to_storage(
    db: Session,
    document_id: str,
    file_content: bytes,
    filename: str,
) -> dict:
    """
    Encrypt and store a document file (R2 private bucket, or local fallback) and
    update document metadata with storage linkage.
    """
    try:
        doc_id = UUID(document_id)
    except (ValueError, AttributeError):
        doc_id = document_id

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("Document not found")

    is_valid, error = validate_file(file_content, filename)
    if not is_valid:
        raise ValueError(error)

    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    onboarding_id = str(doc.onboarding_id)

    # Structured storage key: onboardings/{onboarding_id}/{document_id}.{ext}
    storage_key = storage.storage_path_for(onboarding_id, str(doc.id), file_ext)

    # Encrypt at rest (AES-256-Fernet)
    ciphertext, algo = storage.encrypt_bytes(file_content)

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # Store: R2 private bucket when configured, otherwise local fallback
    if storage.is_r2_configured():
        storage.upload_to_r2(storage_key, ciphertext, content_type)
        file_url = storage.generate_presigned_url(storage_key)
    else:
        storage.upload_local(storage_key, ciphertext)
        file_url = f"local://{storage_key}"

    # Persist metadata linkage (Task: Connect database with stored files)
    doc.file_key = storage_key
    doc.file_name = filename
    doc.file_size = str(len(file_content))
    doc.file_mime_type = content_type
    doc.encryption_algorithm = algo
    doc.status = DocumentStatus.UPLOADED
    doc.uploaded_at = datetime.now(timezone.utc)
    doc.file_url = file_url
    db.commit()

    return {
        "id": str(doc.id),
        "name": doc.name,
        "description": doc.description,
        "instructions": doc.instructions,
        "accepted_formats": doc.accepted_formats,
        "required": doc.required,
        "status": doc.status.value,
        "file_name": doc.file_name,
        "file_key": doc.file_key,
        "file_size": doc.file_size,
        "file_mime_type": doc.file_mime_type,
        "encryption_algorithm": doc.encryption_algorithm,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


def get_document_for_upload(db: Session, document_id: str) -> dict:
    """Retrieve a document for the upload page."""
    try:
        doc_id = UUID(document_id)
    except ValueError:
        raise ValueError("Invalid document ID")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("Document not found")

    return {
        "id": str(doc.id),
        "name": doc.name,
        "description": doc.description,
        "instructions": doc.instructions,
        "accepted_formats": doc.accepted_formats,
        "required": doc.required,
        "status": doc.status.value,
        "file_name": doc.file_name,
        "file_key": doc.file_key,
        "file_size": doc.file_size,
        "file_mime_type": doc.file_mime_type,
        "encryption_algorithm": doc.encryption_algorithm,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════
# US11 — HR document access (short-lived URLs) + manual verification
# ═══════════════════════════════════════════════════════════════════════
# NOTE: verification in this module is MANUAL HR verification only — an HR
# coordinator previews/downloads the file and marks it verified/rejected.
# AI-assisted verification is US12 and stays out of scope for this MVP.

# Short expiry for access URLs — these documents are sensitive (IDs, tax
# forms). 600s (10 min) is enough for HR to view/download once.
ACCESS_URL_EXPIRY_SECONDS = 600


def get_onboarding_detail(db: Session, onboarding_id) -> dict:
    """
    Full detail for the HR detail page (US11): candidate info, onboarding
    status/timestamps, invitation status, and ALL documents including file
    metadata and verification state.

    Raises ValueError('onboarding_not_found') for unknown ids → API maps to 404.
    """
    try:
        oid = UUID(str(onboarding_id))
    except (ValueError, AttributeError):
        raise ValueError("onboarding_not_found")

    onboarding = db.query(Onboarding).filter(Onboarding.id == oid).first()
    if not onboarding:
        raise ValueError("onboarding_not_found")

    candidate = onboarding.candidate
    documents = (
        db.query(Document)
        .filter(Document.onboarding_id == onboarding.id)
        .order_by(Document.created_at.asc())
        .all()
    )

    def _enum_value(v):
        return v.value if hasattr(v, "value") else str(v)

    return {
        "onboarding_id": str(onboarding.id),
        "candidate": {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "position": candidate.position,
        },
        "status": _enum_value(onboarding.status),
        "started_at": onboarding.started_at,
        "completed_at": onboarding.completed_at,
        "created_at": onboarding.created_at,
        "invitation_email_status": _enum_value(onboarding.invitation_email_status),
        "invitation_sent_at": onboarding.invitation_sent_at,
        "documents": [
            {
                "id": str(d.id),
                "name": d.name,
                "description": d.description,
                "instructions": d.instructions,
                "accepted_formats": d.accepted_formats,
                "required": d.required,
                "status": _enum_value(d.status),
                "file_name": d.file_name,
                "file_size": d.file_size,
                "file_mime_type": d.file_mime_type,
                "uploaded_at": d.uploaded_at,
                "verification_status": _enum_value(d.verification_status),
                "verification_note": d.verification_note,
                "verified_at": d.verified_at,
                "verified_by": str(d.verified_by) if d.verified_by else None,
            }
            for d in documents
        ],
    }


def get_document_access_url(db: Session, document_id: str) -> dict:
    """
    Short-lived access URL for preview/download (US11).

    Decrypts NOTHING here and returns NO file bytes — the URL either points
    at the private R2 object (presigned GET) or at the signed local API route
    that streams decrypted bytes (see storage.generate_document_access_url).
    Raises ValueError('document_not_found') / ValueError('no_file_uploaded').
    """
    try:
        doc_id = UUID(document_id)
    except (ValueError, AttributeError):
        raise ValueError("document_not_found")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("document_not_found")

    if not doc.file_key:
        raise ValueError("no_file_uploaded")

    url = storage.generate_document_access_url(
        key=doc.file_key,
        document_id=str(doc.id),
        expires_in=ACCESS_URL_EXPIRY_SECONDS,
    )
    return {
        "document_id": str(doc.id),
        "file_name": doc.file_name,
        "file_mime_type": doc.file_mime_type,
        "access_url": url,
        "expires_in": ACCESS_URL_EXPIRY_SECONDS,
        "storage_backend": "cloudflare_r2" if storage.is_r2_configured() else "local_signed_url",
    }


def serve_document_bytes(db: Session, token: str) -> tuple[bytes, str, str]:
    """
    Local-fallback streaming route (US11): validate the short-lived signed
    token, load the document, decrypt on the fly, return raw bytes.

    Returns (bytes, mime_type, file_name).
    Raises ValueError('invalid_or_expired_token') / ValueError('document_not_found')
    / ValueError('no_file_uploaded') / ValueError('file_missing_on_disk').
    """
    from jose import jwt, JWTError

    from app.core.config import settings
    from app.services.storage import LOCAL_ACCESS_TOKEN_TYPE

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise ValueError("invalid_or_expired_token")
    if payload.get("type") != LOCAL_ACCESS_TOKEN_TYPE:
        raise ValueError("invalid_or_expired_token")

    document_id = payload.get("sub")
    try:
        doc_id = UUID(document_id)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("document_not_found")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("document_not_found")
    if not doc.file_key:
        raise ValueError("no_file_uploaded")

    # Read + decrypt on the fly (local fallback stores ciphertext on disk).
    path = os.path.join(storage.local_fallback_dir(), doc.file_key)
    if not os.path.exists(path):
        raise ValueError("file_missing_on_disk")
    with open(path, "rb") as f:
        ciphertext = f.read()
    try:
        plaintext = storage.decrypt_bytes(ciphertext)
    except Exception:
        raise ValueError("file_missing_on_disk")

    mime = doc.file_mime_type or "application/octet-stream"
    file_name = doc.file_name or f"document-{doc.id}"
    return plaintext, mime, file_name


def update_verification(
    db: Session, document_id: str, verification_status: str, note: str | None, hr_user_id
) -> dict:
    """
    Manual HR verification (US11): set verification_status (+ optional note),
    recording verified_by (authenticated HR user) and verified_at=now.

    Only documents that actually have a file (status uploaded/completed) can
    be verified — a missing/pending document has nothing to verify.
    Raises ValueError('document_not_found' | 'invalid_verification_status' |
    'no_file_uploaded').
    """
    try:
        doc_id = UUID(document_id)
    except (ValueError, AttributeError):
        raise ValueError("document_not_found")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("document_not_found")

    try:
        target = DocumentVerificationStatus(verification_status)
    except ValueError:
        raise ValueError(
            "invalid_verification_status: "
            f"allowed values are {[s.value for s in DocumentVerificationStatus]}"
        )

    if doc.status not in (DocumentStatus.UPLOADED, DocumentStatus.COMPLETED):
        raise ValueError("no_file_uploaded: only uploaded documents can be verified")

    doc.verification_status = target
    doc.verification_note = note
    doc.verified_by = hr_user_id
    doc.verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)

    return {
        "id": str(doc.id),
        "name": doc.name,
        "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        "verification_status": doc.verification_status.value,
        "verification_note": doc.verification_note,
        "verified_at": doc.verified_at,
        "verified_by": str(doc.verified_by) if doc.verified_by else None,
    }
