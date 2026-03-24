"""Object storage client — supports S3/MinIO and local filesystem fallback.

When s3_endpoint_url is provided, uses boto3 for real S3/MinIO operations.
Otherwise falls back to local filesystem (for dev/test environments).
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Any

from backend.core.logger import get_logger

logger = get_logger(__name__)


class StorageClient:
    """S3/MinIO object storage with local filesystem fallback.

    Args:
        base_dir: Local filesystem directory (used in local_mode).
        s3_endpoint_url: MinIO/S3 endpoint URL. If set, enables S3 mode.
        s3_access_key: AWS/MinIO access key.
        s3_secret_key: AWS/MinIO secret key.
        s3_bucket_name: S3 bucket name.
        s3_region: AWS region (default: us-east-1 for MinIO compatibility).
    """

    def __init__(
        self,
        *,
        base_dir: str = "/tmp/research-copilot-uploads",
        s3_endpoint_url: str | None = None,
        s3_access_key: str | None = None,
        s3_secret_key: str | None = None,
        s3_bucket_name: str = "research-copilot",
        s3_region: str = "us-east-1",
    ) -> None:
        self._base_dir = Path(base_dir)
        self._s3_endpoint_url = s3_endpoint_url
        self._s3_bucket_name = s3_bucket_name
        self._s3_client: Any | None = None

        if s3_endpoint_url and s3_access_key and s3_secret_key:
            import boto3

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=s3_endpoint_url,
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                region_name=s3_region,
            )
            logger.info(
                "storage_client_s3_mode",
                endpoint=s3_endpoint_url,
                bucket=s3_bucket_name,
            )
        else:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            logger.info("storage_client_local_mode", base_dir=str(self._base_dir))

    @property
    def local_mode(self) -> bool:
        """Whether the client is using local filesystem fallback."""
        return self._s3_client is None

    async def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a pre-signed URL for PUT upload.

        S3 mode: returns a real presigned PUT URL.
        Local mode: returns a mock API endpoint.
        """
        if self._s3_client is not None:
            url: str = self._s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._s3_bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            return url

        encoded_key = urllib.parse.quote(key)
        return f"/api/v1/documents/upload?key={encoded_key}"

    async def generate_presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a pre-signed URL for GET download.

        S3 mode: returns a real presigned GET URL.
        Local mode: returns a mock download endpoint.
        """
        if self._s3_client is not None:
            url: str = self._s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._s3_bucket_name,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return url

        encoded_key = urllib.parse.quote(key)
        return f"/api/v1/documents/{encoded_key}/download"

    # Keep legacy method for backward compatibility
    async def generate_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> str:
        """Legacy method — delegates to generate_presigned_upload_url."""
        return await self.generate_presigned_upload_url(key, content_type, expires_in)

    async def head_object(self, key: str) -> bool:
        """Check if object exists."""
        if self._s3_client is not None:
            try:
                self._s3_client.head_object(
                    Bucket=self._s3_bucket_name,
                    Key=key,
                )
                return True
            except Exception:
                return False

        return (self._base_dir / key).exists()

    async def delete_object(self, key: str) -> None:
        """Delete an object."""
        if self._s3_client is not None:
            self._s3_client.delete_object(
                Bucket=self._s3_bucket_name,
                Key=key,
            )
            return

        target = self._base_dir / key
        if target.exists():
            target.unlink()
