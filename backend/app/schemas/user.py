from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole, AuthProvider


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.VENDOR


class UserCreate(UserBase):
    email: EmailStr
    password: str


class UserCreateOAuth(UserBase):
    email: EmailStr
    auth_provider: AuthProvider
    provider_id: str


class UserUpdate(UserBase):
    password: Optional[str] = None


class UserRead(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Phase 1 name, still used by crud.user. Kept as an alias so existing imports
# keep working.
User = UserRead


class MeResponse(BaseModel):
    """Identity of the authenticated caller, plus a flattened view of their
    vendor profile when one exists.

    `vendor_id`/`preferred_language` are None for consumers and for vendors
    who have registered a login but not yet completed stall onboarding --
    which is exactly the signal the mobile client branches on.
    """

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    vendor_id: Optional[int] = None
    preferred_language: Optional[str] = None
