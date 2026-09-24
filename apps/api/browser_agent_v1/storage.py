"""Object storage helpers for Browser Agent V1 artifacts."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from uuid import UUID, uuid4

try:
    from minio import Minio
except ModuleNotFoundError:  # pragma: no cover - slim test env fallback
    class Minio:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("minio is required for Browser Agent V1 artifact storage")

from core.config import settings


def _minio_client() -> Minio:
    endpoint = settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
    secure = settings.MINIO_ENDPOINT.startswith("https://")
    return Minio(endpoint, access_key=settings.MINIO_ACCESS_KEY, secret_key=settings.MINIO_SECRET_KEY, secure=secure)


def _ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def artifact_object_key(*, run_id: UUID, artifact_type: str, content_type: str) -> str:
    extension = "bin"
    lowered = content_type.lower()
    if "png" in lowered:
        extension = "png"
    elif "json" in lowered:
        extension = "json"
    elif "html" in lowered:
        extension = "html"
    return f"{settings.BROWSER_AGENT_V1_ARTIFACT_PREFIX.strip('/')}/{run_id}/{artifact_type}/{uuid4().hex}.{extension}"


def put_artifact_bytes(*, run_id: UUID, artifact_type: str, content_type: str, payload: bytes) -> tuple[str, dict[str, str | int]]:
    """Upload one artifact payload to object storage and return metadata."""

    client = _minio_client()
    _ensure_bucket(client)
    object_key = artifact_object_key(run_id=run_id, artifact_type=artifact_type, content_type=content_type)
    client.put_object(
        settings.MINIO_BUCKET,
        object_key,
        BytesIO(payload),
        length=len(payload),
        content_type=content_type,
    )
    return object_key, {"bucket": settings.MINIO_BUCKET, "byte_length": len(payload), "content_type": content_type}


def get_artifact_url(storage_path: str | None, *, expires_minutes: int = 30) -> str | None:
    if not storage_path:
        return None
    client = _minio_client()
    return client.presigned_get_object(settings.MINIO_BUCKET, storage_path, expires=timedelta(minutes=expires_minutes))
