"""
PetCircle — Unified Storage Service (GCP + Supabase)

Provides a single abstraction over document file storage. GCP Cloud Storage
is the primary backend; Supabase is the silent fallback if GCP is unavailable
or misconfigured.

Design rules:
    - GCP is tried first on every upload. Any exception → fallback to Supabase.
    - No exception is ever raised from upload_file unless BOTH backends fail.
    - GCP client is initialized once and cached. Missing credentials are treated
      as "GCP unavailable" — the app starts cleanly without them.
    - Downloads route to the backend recorded in documents.storage_backend.
      If the recorded backend fails, the other is tried as an emergency fallback.
    - All GCP SDK calls run in asyncio.run_in_executor() to avoid blocking
      the event loop (same pattern as existing Supabase calls).

Scope:
    - This service handles DOCUMENTS only (documents table).
    - Pet photos (pets.photo_path) continue using upload_to_supabase directly
      in onboarding services — they are out of scope for GCP migration.
"""

import asyncio
import base64
import json
import logging

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

# --- Module-level GCP state ---
# Client and availability are resolved once on first use, then cached.
_gcp_client = None
_gcp_available: bool | None = None  # None = not yet probed


def _get_gcp_client():
    """
    Return a cached GCP storage client, or None if GCP is not configured.

    Decodes GCP_CREDENTIALS_JSON (base64-encoded service account JSON) from
    settings. On any failure (missing env, malformed JSON, invalid credentials)
    returns None and logs a warning. Never raises.
    """
    global _gcp_client, _gcp_available

    if _gcp_available is not None:
        # Already probed — return cached result.
        return _gcp_client

    if not settings.GCP_CREDENTIALS_JSON or not settings.GCP_BUCKET_NAME:
        logger.info(
            "GCP storage not configured (GCP_CREDENTIALS_JSON or GCP_BUCKET_NAME missing) "
            "— all document uploads will use Supabase"
        )
        _gcp_available = False
        return None

    try:
        from google.cloud import storage
        from google.oauth2 import service_account

        # Decode base64 → JSON → credentials object.
        credentials_dict = json.loads(
            base64.b64decode(settings.GCP_CREDENTIALS_JSON).decode("utf-8")
        )
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        _gcp_client = storage.Client(
            credentials=credentials,
            project=credentials_dict.get("project_id"),
        )
        _gcp_available = True
        logger.info(
            "GCP storage client initialized: bucket=%s, project=%s",
            settings.GCP_BUCKET_NAME,
            credentials_dict.get("project_id"),
        )
        return _gcp_client

    except ImportError:
        logger.warning(
            "google-cloud-storage package not installed — GCP storage unavailable. "
            "Install with: pip install google-cloud-storage"
        )
    except Exception as e:
        logger.warning(
            "GCP client initialization failed — falling back to Supabase for all uploads. "
            "Error: %s",
            str(e),
        )

    _gcp_available = False
    return None


def is_gcp_available() -> bool:
    """
    Return True if GCP is configured and the client initialized successfully.

    Probes on first call, returns cached result thereafter.
    """
    _get_gcp_client()
    return bool(_gcp_available)


async def _upload_to_gcp(
    file_content: bytes,
    storage_path: str,
    mime_type: str,
) -> str:
    """
    Upload file bytes to GCP Cloud Storage.

    Runs the sync GCP SDK call in a thread pool executor to avoid blocking
    the event loop (same pattern as existing Supabase upload).

    Args:
        file_content: Raw file bytes.
        storage_path: Object path within the bucket.
        mime_type: Content-Type for the uploaded object.

    Returns:
        storage_path on success.

    Raises:
        RuntimeError: If the GCP upload fails.
    """
    gcp_client = _get_gcp_client()
    bucket_name = settings.GCP_BUCKET_NAME

    def _sync_gcp_upload():
        bucket = gcp_client.bucket(bucket_name)
        blob = bucket.blob(storage_path)
        blob.upload_from_string(file_content, content_type=mime_type)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_gcp_upload)

        logger.info(
            "File uploaded to GCP: bucket=%s, path=%s, mime=%s, size=%d",
            bucket_name,
            storage_path,
            mime_type,
            len(file_content),
        )
        return storage_path

    except Exception as e:
        logger.error(
            "GCP upload failed: bucket=%s, path=%s, error=%s",
            bucket_name,
            storage_path,
            str(e),
        )
        raise RuntimeError(f"GCP upload failed: {e}") from e


async def _download_from_gcp(storage_path: str) -> bytes | None:
    """
    Download file bytes from GCP Cloud Storage.

    Args:
        storage_path: Object path within the bucket.

    Returns:
        Raw file bytes, or None on failure.
    """
    gcp_client = _get_gcp_client()
    if gcp_client is None:
        return None

    bucket_name = settings.GCP_BUCKET_NAME

    def _sync_gcp_download() -> bytes:
        bucket = gcp_client.bucket(bucket_name)
        blob = bucket.blob(storage_path)
        return blob.download_as_bytes()

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _sync_gcp_download)
        logger.info(
            "File downloaded from GCP: path=%s, size=%d",
            storage_path, len(data),
        )
        return data

    except Exception as e:
        logger.error(
            "GCP download failed: path=%s, error=%s",
            storage_path, str(e),
        )
        return None


async def upload_file(
    file_content: bytes,
    storage_path: str,
    mime_type: str,
) -> tuple[str, str]:
    """
    Upload a file to storage (GCP primary, Supabase fallback).

    Tries GCP first. If GCP is unavailable or raises any exception,
    silently falls back to Supabase and logs a warning.

    Args:
        file_content: Raw file bytes.
        storage_path: Path within the bucket ({user_id}/{pet_id}/{filename}).
        mime_type: MIME type for content-type header.

    Returns:
        Tuple of (storage_path, backend) where backend is 'gcp' or 'supabase'.
        The storage_path is identical for both backends.

    Raises:
        RuntimeError: Only if BOTH GCP and Supabase fail.
    """
    # --- Try GCP first ---
    if is_gcp_available():
        try:
            await _upload_to_gcp(file_content, storage_path, mime_type)
            return storage_path, "gcp"
        except Exception as e:
            logger.warning(
                "GCP upload failed, falling back to Supabase: path=%s, error=%s",
                storage_path, str(e),
            )

    # --- Fall back to Supabase ---
    # Import here to avoid circular import; document_upload owns the Supabase client.
    from app.services.document_upload import upload_to_supabase
    await upload_to_supabase(file_content, storage_path, mime_type)
    return storage_path, "supabase"


async def download_file(
    storage_path: str,
    backend: str = "supabase",
) -> bytes | None:
    """
    Download file bytes from the specified storage backend.

    If backend='gcp' but GCP fails, tries Supabase as emergency fallback
    (guards against partial-sync state where DB says 'gcp' but file hasn't
    been fully migrated yet).

    Args:
        storage_path: Path within the bucket.
        backend: 'gcp' or 'supabase' — from documents.storage_backend.

    Returns:
        Raw file bytes, or None if download fails from all backends.
    """
    if backend == "gcp":
        data = await _download_from_gcp(storage_path)
        if data is not None:
            return data
        # Emergency fallback: try Supabase in case the GCP record is stale.
        logger.warning(
            "GCP download failed for gcp-backend doc, trying Supabase fallback: path=%s",
            storage_path,
        )
        from app.services.document_upload import _download_supabase_raw
        return await _download_supabase_raw(storage_path)

    # Default: Supabase
    from app.services.document_upload import _download_supabase_raw
    return await _download_supabase_raw(storage_path)


async def _delete_from_gcp(storage_path: str) -> bool:
    """
    Delete a file from GCP Cloud Storage.

    Args:
        storage_path: Object path within the bucket.

    Returns:
        True on success, False on failure.
    """
    gcp_client = _get_gcp_client()
    if gcp_client is None:
        return False

    bucket_name = settings.GCP_BUCKET_NAME

    def _sync_gcp_delete():
        bucket = gcp_client.bucket(bucket_name)
        blob = bucket.blob(storage_path)
        blob.delete()

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_gcp_delete)
        logger.info("Deleted from GCP: path=%s", storage_path)
        return True
    except Exception as e:
        logger.error("GCP delete failed: path=%s, error=%s", storage_path, str(e))
        return False


async def delete_file(storage_path: str, backend: str) -> bool:
    """
    Delete a document file from the appropriate storage backend.

    Routes to GCP or Supabase based on the backend argument.
    Never raises — returns False on failure so callers can proceed with DB cleanup.

    Args:
        storage_path: Object path within the bucket.
        backend: 'gcp' or 'supabase'.

    Returns:
        True on success, False on failure.
    """
    if backend == "gcp":
        return await _delete_from_gcp(storage_path)
    return await delete_from_supabase(storage_path)


async def delete_from_supabase(storage_path: str) -> bool:
    """
    Delete a file from Supabase storage bucket.

    Used by the sync job after confirming the GCP copy exists.

    Args:
        storage_path: Path within the Supabase bucket.

    Returns:
        True on success, False on failure.
    """
    import asyncio

    from app.services.document_upload import _get_supabase_client

    bucket_name = settings.SUPABASE_BUCKET_NAME

    def _sync_delete():
        client = _get_supabase_client()
        client.storage.from_(bucket_name).remove([storage_path])

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_delete)
        logger.info("Deleted from Supabase: path=%s", storage_path)
        return True
    except Exception as e:
        logger.error("Supabase delete failed: path=%s, error=%s", storage_path, str(e))
        return False


async def sync_document_to_gcp(
    db: Session,
    document_id: str,
    file_path: str,
    mime_type: str,
) -> bool:
    """
    Migrate a single document from Supabase to GCP.

    Flow:
        1. Download file bytes from Supabase.
        2. Upload bytes to GCP.
        3. Verify GCP object exists (blob.exists() check).
        4. Update documents.storage_backend = 'gcp' in DB.
        5. Delete from Supabase.

    Atomic: DB is only updated after confirmed GCP upload + verification.
    If any step fails, the document stays in Supabase and False is returned.

    Args:
        db: SQLAlchemy database session.
        document_id: UUID string of the document record.
        file_path: Storage path of the file.
        mime_type: MIME type of the file.

    Returns:
        True on successful migration, False on any failure.
    """
    from sqlalchemy import text

    from app.services.document_upload import _download_supabase_raw

    # Step 1: Download from Supabase.
    file_bytes = await _download_supabase_raw(file_path)
    if file_bytes is None:
        logger.error("sync: Supabase download failed: doc_id=%s, path=%s", document_id, file_path)
        return False

    # Step 2: Upload to GCP.
    try:
        await _upload_to_gcp(file_bytes, file_path, mime_type)
    except Exception as e:
        logger.error(
            "sync: GCP upload failed: doc_id=%s, path=%s, error=%s",
            document_id, file_path, str(e),
        )
        return False

    # Step 3: Verify GCP object exists.
    gcp_client = _get_gcp_client()
    if gcp_client is None:
        logger.error("sync: GCP client lost after upload: doc_id=%s", document_id)
        return False

    def _check_exists() -> bool:
        bucket = gcp_client.bucket(settings.GCP_BUCKET_NAME)
        blob = bucket.blob(file_path)
        return blob.exists()

    try:
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, _check_exists)
        if not exists:
            logger.error(
                "sync: GCP blob not found after upload: doc_id=%s, path=%s",
                document_id, file_path,
            )
            return False
    except Exception as e:
        logger.error(
            "sync: GCP existence check failed: doc_id=%s, error=%s",
            document_id, str(e),
        )
        return False

    # Step 4: Update DB.
    try:
        db.execute(
            text("UPDATE documents SET storage_backend = 'gcp' WHERE id = :doc_id"),
            {"doc_id": document_id},
        )
        db.commit()
    except Exception as e:
        logger.error(
            "sync: DB update failed: doc_id=%s, error=%s",
            document_id, str(e),
        )
        db.rollback()
        return False

    # Step 5: Delete from Supabase.
    deleted = await delete_from_supabase(file_path)
    if not deleted:
        # Non-fatal: GCP has the file and DB is updated. Supabase cleanup can
        # be retried — the sync job will skip this doc next run (storage_backend='gcp').
        logger.warning(
            "sync: Supabase delete failed (non-fatal): doc_id=%s, path=%s",
            document_id, file_path,
        )

    logger.info("sync: migrated to GCP: doc_id=%s, path=%s", document_id, file_path)
    return True
