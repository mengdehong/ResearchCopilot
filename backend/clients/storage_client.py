"""Object storage client — mock implementation for MVP."""

from __future__ import annotations

from pathlib import Path


class StorageClient:
    """S3/MinIO object storage. MVP: local filesystem fallback.

    Phase 8: replace with real S3/MinIO SDK.
    """

    def __init__(self, *, base_dir: str = "/tmp/research-copilot-uploads") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def generate_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate pre-signed upload URL.

        MVP: returns a local file path as pseudo-URL.
        """
        return f"file://{self._base_dir / key}?expires={expires_in}"

    async def head_object(self, key: str) -> bool:
        """Check if object exists."""
        return (self._base_dir / key).exists()

    async def delete_object(self, key: str) -> None:
        """Delete an object."""
        target = self._base_dir / key
        if target.exists():
            target.unlink()
