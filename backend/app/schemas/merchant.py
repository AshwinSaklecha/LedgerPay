from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, HttpUrl


class MerchantRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    webhook_url: HttpUrl | None = None


class MerchantRegisterResponse(BaseModel):
    id: UUID
    name: str
    email: str
    webhook_url: str | None
    api_key: str          # plaintext — shown exactly once
    created_at: datetime


class MerchantResponse(BaseModel):
    id: UUID
    name: str
    email: str
    webhook_url: str | None
    is_active: bool
    created_at: datetime
