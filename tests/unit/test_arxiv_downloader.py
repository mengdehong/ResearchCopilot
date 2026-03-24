"""ArXiv PDF 下载器单元测试。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.arxiv_downloader import download_arxiv_pdf


class TestDownloadArxivPdf:
    """download_arxiv_pdf 单元测试。"""

    @patch("backend.services.arxiv_downloader.httpx.get")
    def test_downloads_pdf_to_storage_dir(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """成功下载 PDF 并存储到指定目录。"""
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 fake content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = download_arxiv_pdf("2301.00001v1", tmp_path)

        assert result.exists()
        assert result.name == "2301.00001v1.pdf"
        assert result.read_bytes() == b"%PDF-1.4 fake content"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "2301.00001v1.pdf" in call_args.args[0]

    @patch("backend.services.arxiv_downloader.httpx.get")
    def test_returns_cached_file_without_download(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """已存在的 PDF 直接返回，不调用 httpx。"""
        cached = tmp_path / "2301.00001v1.pdf"
        cached.write_bytes(b"cached")

        result = download_arxiv_pdf("2301.00001v1", tmp_path)

        assert result == cached
        mock_get.assert_not_called()

    @patch("backend.services.arxiv_downloader.httpx.get")
    def test_sanitizes_arxiv_id_with_slash(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """包含斜杠的 arxiv_id 转换为下划线。"""
        mock_response = MagicMock()
        mock_response.content = b"%PDF"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = download_arxiv_pdf("hep-th/9901001", tmp_path)

        assert result.name == "hep-th_9901001.pdf"

    @patch("backend.services.arxiv_downloader.httpx.get")
    def test_raises_on_http_error(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """HTTP 错误应向上传播。"""
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            download_arxiv_pdf("invalid_id", tmp_path)

    @patch("backend.services.arxiv_downloader.httpx.get")
    def test_creates_storage_dir_if_missing(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """存储目录不存在时自动创建。"""
        mock_response = MagicMock()
        mock_response.content = b"%PDF"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        nested_dir = tmp_path / "sub" / "dir"
        result = download_arxiv_pdf("2401.00001", nested_dir)

        assert result.exists()
        assert nested_dir.exists()
