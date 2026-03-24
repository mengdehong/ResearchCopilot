"""StorageClient — TDD tests for S3/MinIO presigned URL support.

Tests both local_mode (filesystem fallback) and S3 mode (boto3).
"""

from unittest.mock import MagicMock


class TestStorageClientLocalMode:
    """When s3_endpoint_url is not set, use local filesystem fallback."""

    async def test_generate_upload_url_returns_local_path(self) -> None:
        from backend.clients.storage_client import StorageClient

        client = StorageClient(base_dir="/tmp/test-uploads")
        url = await client.generate_presigned_upload_url(
            key="docs/test.pdf", content_type="application/pdf"
        )
        assert "/api/v1/documents/upload" in url
        assert "test.pdf" in url

    async def test_generate_download_url_returns_local_path(self) -> None:
        from backend.clients.storage_client import StorageClient

        client = StorageClient(base_dir="/tmp/test-uploads")
        url = await client.generate_presigned_download_url(key="docs/test.pdf")
        assert "/api/v1/documents" in url
        assert "download" in url


class TestStorageClientS3Mode:
    """When s3_endpoint_url is set, use boto3 S3 client."""

    async def test_generate_upload_url_returns_s3_presigned(self) -> None:
        from backend.clients.storage_client import StorageClient

        client = StorageClient(
            s3_endpoint_url="http://minio:9000",
            s3_access_key="minioadmin",
            s3_secret_key="minioadmin",
            s3_bucket_name="test-bucket",
        )
        url = await client.generate_presigned_upload_url(
            key="docs/test.pdf", content_type="application/pdf"
        )
        # S3 presigned URLs contain the bucket and key
        assert "test-bucket" in url or "docs/test.pdf" in url
        assert url.startswith("http")

    async def test_generate_download_url_returns_s3_presigned(self) -> None:
        from backend.clients.storage_client import StorageClient

        client = StorageClient(
            s3_endpoint_url="http://minio:9000",
            s3_access_key="minioadmin",
            s3_secret_key="minioadmin",
            s3_bucket_name="test-bucket",
        )
        url = await client.generate_presigned_download_url(key="docs/test.pdf")
        assert url.startswith("http")

    async def test_head_object_delegates_to_s3(self) -> None:
        from backend.clients.storage_client import StorageClient

        client = StorageClient(
            s3_endpoint_url="http://minio:9000",
            s3_access_key="minioadmin",
            s3_secret_key="minioadmin",
            s3_bucket_name="test-bucket",
        )
        # Mock the internal s3 client
        mock_s3 = MagicMock()
        mock_s3.head_object = MagicMock(return_value={})
        client._s3_client = mock_s3

        result = await client.head_object("docs/test.pdf")
        assert result is True
        mock_s3.head_object.assert_called_once()

    async def test_delete_object_delegates_to_s3(self) -> None:
        from backend.clients.storage_client import StorageClient

        client = StorageClient(
            s3_endpoint_url="http://minio:9000",
            s3_access_key="minioadmin",
            s3_secret_key="minioadmin",
            s3_bucket_name="test-bucket",
        )
        mock_s3 = MagicMock()
        mock_s3.delete_object = MagicMock(return_value={})
        client._s3_client = mock_s3

        await client.delete_object("docs/test.pdf")
        mock_s3.delete_object.assert_called_once()
