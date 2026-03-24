"""EmailService 抽象 + Resend 实现单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from backend.clients.email_service.base import EmailService
from backend.clients.email_service.resend_client import ResendEmailService


class TestEmailServiceProtocol:
    """EmailService Protocol 合规性测试。"""

    def test_resend_implements_protocol(self) -> None:
        """ResendEmailService 应符合 EmailService Protocol。"""
        service = ResendEmailService(
            api_key="test", from_email="a@b.com", frontend_url="http://localhost"
        )
        assert isinstance(service, EmailService)


class TestResendEmailService:
    """ResendEmailService 实现测试。"""

    @pytest.fixture
    def service(self) -> ResendEmailService:
        return ResendEmailService(
            api_key="re_test_key",
            from_email="noreply@test.com",
            frontend_url="http://localhost:5173",
        )

    @patch("backend.clients.email_service.resend_client.resend")
    async def test_send_verification_email(
        self, mock_resend: MagicMock, service: ResendEmailService
    ) -> None:
        """发送验证邮件应调用 resend.Emails.send。"""
        mock_resend.Emails.send = MagicMock(return_value={"id": "email_123"})

        await service.send_verification_email(to="user@test.com", token="verify-token-abc")

        mock_resend.Emails.send.assert_called_once()
        call_args = mock_resend.Emails.send.call_args
        params = call_args[0][0] if call_args[0] else call_args[1]
        assert params["to"] == ["user@test.com"]
        assert params["from"] == "noreply@test.com"
        assert "verify-token-abc" in params["html"]

    @patch("backend.clients.email_service.resend_client.resend")
    async def test_send_password_reset_email(
        self, mock_resend: MagicMock, service: ResendEmailService
    ) -> None:
        """发送重置密码邮件应调用 resend.Emails.send。"""
        mock_resend.Emails.send = MagicMock(return_value={"id": "email_456"})

        await service.send_password_reset_email(to="user@test.com", token="reset-token-xyz")

        mock_resend.Emails.send.assert_called_once()
        call_args = mock_resend.Emails.send.call_args
        params = call_args[0][0] if call_args[0] else call_args[1]
        assert params["to"] == ["user@test.com"]
        assert "reset-token-xyz" in params["html"]
