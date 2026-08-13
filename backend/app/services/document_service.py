import os
import mimetypes
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Document, DocumentStatus

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
    # Check file size
    if len(file_content) > MAX_FILE_SIZE_BYTES:
        return False, f"File size exceeds {MAX_FILE_SIZE_MB}MB limit"

    if len(file_content) == 0:
        return False, "Uploaded file is empty"

    # Check file extension
    ext = None
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    if ext and f".{ext}" not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type. Allowed: PDF, JPG, PNG, GIF"

    # Verify extension maps to an allowed MIME type
    expected_mime = MIMETYPE_BY_EXT.get(f".{ext}")
    # Also check what the browser-sent Content-Type says (mimetypes is not always reliable)
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        # Fall back to extension-based detection
        mime_type = expected_mime

    if mime_type not in MIMETYPE_BY_EXT.values():
        return False, "Unsupported file type. Allowed: PDF, JPG, PNG, GIF"

    # Verify extension is consistent with the detected MIME (allow .jpg/.jpeg for jpeg)
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
    Upload a file to Cloudflare R2 and update document metadata.
    Falls back to local storage if R2 is not configured.
    """
    try:
        doc_id = UUID(document_id)
    except (ValueError, AttributeError):
        doc_id = document_id  # Let the query fail with 404 if truly invalid

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError("Document not found")

    # Validate file
    is_valid, error = validate_file(file_content, filename)
    if not is_valid:
        raise ValueError(error)

    # Generate unique storage key
    import uuid as uuid_module
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    storage_key = f"{uuid_module.uuid4().hex}.{file_ext}"

    # Try R2 storage; fall back to local file storage
    stored = False
    if settings.R2_BUCKET_NAME and settings.R2_ACCESS_KEY_ID:
        try:
            stored = _upload_to_r2(file_content, storage_key)
        except Exception as e:
            print(f"R2 upload failed, falling back to local: {e}")

    if not stored:
        # Fallback: local storage in uploads directory
        upload_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "uploads",
        )
        os.makedirs(upload_dir, exist_ok=True)
        local_path = os.path.join(upload_dir, storage_key)
        with open(local_path, "wb") as f:
            f.write(file_content)

    # Update document metadata
    doc.file_key = storage_key
    doc.file_name = filename
    doc.status = DocumentStatus.UPLOADED
    doc.uploaded_at = datetime.now(timezone.utc)
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
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


def _upload_to_r2(file_content: bytes, key: str) -> bool:
    """Upload file to Cloudflare R2 via boto3/S3-compatible API."""
    import boto3
    from botocore.config import Config

    if not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
        return False

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    s3.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=file_content,
        ContentType=mimetypes.guess_type(key)[0] or "application/octet-stream",
    )
    return True


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
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }
