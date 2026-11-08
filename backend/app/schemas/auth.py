from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

class UserRegister(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="Valid email address")
    password: str = Field(..., min_length=10, description="Password must be at least 10 chars with uppercase, lowercase, digit, and symbol")

class UserLogin(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="User email address")
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool = False

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10, description="New password must meet complexity rules")

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    tier: str
    is_active: bool
    must_change_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None
    tier: Optional[str] = None
