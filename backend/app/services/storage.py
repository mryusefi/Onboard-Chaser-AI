"""Storage utilities for US04: secure document storage.

Implements:
- Deterministic per-onboarding storage structure (folder layout)
- AES encryption at rest (Fernet symmetric) with a derived key
- Cloudflare R2 upload with private bucket semantics (no public ACL)
- Local filesystem fallback with the same structure

Encryption key is derived from settings.SECRET_KEY. In production you should
store a dedicated STORAGE_ENCRYPTION_KEY in the environment / secrets manager.
"""
import os
import base64
import uuid as uuid_module
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from SECRET_KEY (stable per deployment)."""
    import hashlib
    # Use SHA-256 of SECRET_KEY as the HKDF input keying material
    ikm = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"onboard-chaser-storage-v1",
        info=b"document-encryption",
    )
    return base64.urlsafe_b64encode(hkdf.derive(ikm))


def get_fernet() -> Fernet:
    return Fernet(_derive_key())


def encrypt_bytes(data: bytes) -> tuple[bytes, str]:
    """Encrypt raw bytes. Returns (ciphertext, algorithm_label)."""
    fernet = get_fernet()
    ct = fernet.encrypt(data)
    return ct, "AES-256-Fernet"


def decrypt_bytes(ciphertext: bytes) -> bytes:
    """Decrypt ciphertext produced by encrypt_bytes."""
    fernet = get_fernet()
    return fernet.decrypt(ciphertext)


def storage_path_for(onboarding_id: str, document_id: str, ext: str) -> str:
    """
    Build a structured storage key:
        onboardings/{onboarding_id}/{document_id}.{ext}
    This keeps documents logically grouped per onboarding and isolated per file.
    """
    safe_ext = ext.lower().lstrip(".")
    return f"onboardings/{onboarding_id}/{document_id}.{safe_ext}"


_PLACEHOLDER_PREFIXES = ("your_", "change-", "placeholder", "xxx", "CHANGEME")


def is_r2_configured() -> bool:
    """True only when all required R2 credentials are REAL values (not placeholders)."""
    for val in (
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
        settings.R2_BUCKET_NAME,
        settings.R2_ENDPOINT_URL,
    ):
        if not val or val.lower().startswith(_PLACEHOLDER_PREFIXES):
            return False
    return True


def upload_to_r2(key: str, data: bytes, content_type: str) -> None:
    """
    Upload encrypted bytes to R2 as a PRIVATE object (no public ACL, no
    public-read). Download access is granted only via presigned URLs.
    """
    import boto3
    from botocore.config import Config

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
        Body=data,
        ContentType=content_type,
        # Explicitly private — no public-read ACL; presigned URLs for access
        ACL="private",
    )


def generate_presigned_url(key: str, expires_in: int = 900) -> str:
    """Generate a short-lived presigned GET URL for a private R2 object."""
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )


def local_fallback_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "uploads",
    )


def upload_local(key: str, data: bytes) -> None:
    """Fallback: store encrypted bytes under the structured key locally."""
    root = local_fallback_dir()
    target = os.path.join(root, key)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(data)
