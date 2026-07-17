"""Build the configured document storage adapter.

Shared by the API layer and the seed so both resolve the same backend from settings.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.modules.documents.application.ports import DocumentStoragePort
from app.modules.documents.infrastructure.local_storage import LocalDocumentStorage
from app.modules.documents.infrastructure.s3_storage import S3DocumentStorage


def build_document_storage(settings: Settings) -> DocumentStoragePort:
    if settings.document_storage_backend == "s3":
        if not settings.s3_bucket or not settings.s3_access_key or not settings.s3_secret_key:
            raise RuntimeError("S3 document storage requires bucket and credentials")
        return S3DocumentStorage(
            endpoint_url=settings.s3_endpoint_url,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key.get_secret_value(),
            secret_key=settings.s3_secret_key.get_secret_value(),
            region=settings.s3_region,
        )
    return LocalDocumentStorage(Path(settings.document_storage_root))
