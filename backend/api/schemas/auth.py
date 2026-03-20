"""Auth schemas — JWT payload and user info DTOs."""

import uuid

from pydantic import BaseModel, EmailStr


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: uuid.UUID
    exp: int


class UserInfo(BaseModel):
    """Public user information response."""

    id: uuid.UUID
    email: str
    display_name: str


class RegisterRequest(BaseModel):
    """注册请求。"""

    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """登录/注册成功响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class TokenResponse(BaseModel):
    """Token 刷新响应。"""

    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    """邮箱验证请求。"""

    token: str


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求。"""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""

    token: str
    new_password: str


class MessageResponse(BaseModel):
    """通用消息响应。"""

    message: str
