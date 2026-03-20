"""Resend 邮件服务实现。"""

import resend

from backend.core.logger import get_logger

logger = get_logger(__name__)


class ResendEmailService:
    """基于 Resend 的邮件发送服务。"""

    def __init__(self, api_key: str, from_email: str, frontend_url: str) -> None:
        self._from_email = from_email
        self._frontend_url = frontend_url
        resend.api_key = api_key

    async def send_verification_email(self, to: str, token: str) -> None:
        """发送邮箱验证邮件。"""
        verify_url = f"{self._frontend_url}/verify-email?token={token}"
        params = {
            "from": self._from_email,
            "to": [to],
            "subject": "Research Copilot — 验证您的邮箱",
            "html": (
                f"<h2>欢迎注册 Research Copilot</h2>"
                f"<p>请点击以下链接验证您的邮箱地址：</p>"
                f'<p><a href="{verify_url}">验证邮箱</a></p>'
                f"<p>此链接 30 分钟内有效。</p>"
                f"<p>如果您未注册过 Research Copilot，请忽略此邮件。</p>"
                f"<hr><p style='color:#999;font-size:12px'>token: {token}</p>"
            ),
        }
        result = resend.Emails.send(params)
        logger.info("verification_email_sent", to=to, email_id=result.get("id"))

    async def send_password_reset_email(self, to: str, token: str) -> None:
        """发送密码重置邮件。"""
        reset_url = f"{self._frontend_url}/reset-password?token={token}"
        params = {
            "from": self._from_email,
            "to": [to],
            "subject": "Research Copilot — 重置密码",
            "html": (
                f"<h2>密码重置请求</h2>"
                f"<p>您正在重置 Research Copilot 的登录密码。</p>"
                f'<p><a href="{reset_url}">点击此链接重置密码</a></p>'
                f"<p>此链接 30 分钟内有效。</p>"
                f"<p>如果您未请求重置密码，请忽略此邮件。</p>"
                f"<hr><p style='color:#999;font-size:12px'>token: {token}</p>"
            ),
        }
        result = resend.Emails.send(params)
        logger.info("password_reset_email_sent", to=to, email_id=result.get("id"))
