"""EmailService 抽象协议 — 邮件发送统一接口。"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailService(Protocol):
    """邮件发送服务协议。

    实现此协议以支持不同邮件提供商（Resend、AWS SES 等）。
    """

    async def send_verification_email(self, to: str, token: str) -> None:
        """发送邮箱验证邮件。"""
        ...

    async def send_password_reset_email(self, to: str, token: str) -> None:
        """发送密码重置邮件。"""
        ...
