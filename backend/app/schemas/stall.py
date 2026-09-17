"""Pydantic schemas for stalls."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StallBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    food_category: Optional[str] = Field(default=None, max_length=120)
    address: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Stall name cannot be blank")
        return v

    @field_validator("food_category", "address")
    @classmethod
    def _strip_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class StallCreate(StallBase):
    """Payload for registering a stall.

    `latitude`/`longitude` are optional: a vendor may only know their street
    address, and the hygiene map phase can geocode later.
    """


class StallUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    food_category: Optional[str] = Field(default=None, max_length=120)
    address: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class StallQrRead(BaseModel):
    """Everything the vendor's "My QR code" screen needs.

    `public_url` is what the QR image encodes, and is returned separately so
    the screen can show the link as text -- a vendor whose sticker is damaged
    can read or share it directly.
    """

    stall_id: int
    code: str
    public_url: str
    """Absolute frontend URL a consumer lands on."""

    image_url: str
    """Root-relative path to the PNG on this API, e.g.
    /api/v1/stalls/3/qr.png. A separate absolute download URL is not needed:
    the client already knows the API origin."""


class StallRead(StallBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    # Derived from the stall's active row in `qr_codes` (see models/stall.py).
    # Optional because a stall whose only code was revoked has no active one.
    # The field is kept on this schema so the API contract is unchanged from
    # Phase 1, when it was a column.
    qr_code_id: Optional[str] = None
    hygiene_score: Optional[float] = None
    # Replaces the Phase 1 `is_flagged` integer. Derived from the flags table,
    # so it cannot disagree with the flags a reviewer actually raised.
    has_open_flag: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
