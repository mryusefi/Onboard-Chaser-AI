import os
import mimetypes
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Document, DocumentStatus
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
