"""Pydantic schemas for vendors and stall onboarding."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.schemas.stall import StallCreate, StallRead


def validate_language(v: Optional[str]) -> Optional[str]:
    """Restrict to configured languages.

    Driven by settings.SUPPORTED_LANGUAGES rather than a hardcoded list, so
    adding a language is a config change plus seed data, not a code change.
    """
    if v is None:
        return None
    v = v.strip().lower()
    if v not in settings.SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{v}'. "
            f"Supported: {', '.join(settings.SUPPORTED_LANGUAGES)}"
        )
    return v


class VendorBase(BaseModel):
    phone_number: Optional[str] = Field(default=None, max_length=20)
    preferred_language: str = "en"

    @field_validator("preferred_language")
    @classmethod
    def _check_language(cls, v: str) -> str:
        return validate_language(v)


class VendorRead(VendorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: Optional[datetime] = None
    full_name: Optional[str] = None
    email: Optional[str] = None


class VendorOnboardRequest(BaseModel):
    """Everything needed to register a vendor profile and their first stall.

    Sent as one request so a half-registered vendor (profile but no stall, or
    vice versa) can never be persisted -- see services/vendors/service.py.
    """

    phone_number: Optional[str] = Field(default=None, max_length=20)
    preferred_language: str = "en"
    stall: StallCreate
    # Free-text "products used" from the onboarding form. Populates
    # food_items, which is descriptive metadata only -- the authoritative
    # product record comes from label scans.
    food_items: List[str] = Field(default_factory=list)

    @field_validator("preferred_language")
    @classmethod
    def _check_language(cls, v: str) -> str:
        return validate_language(v)

    @field_validator("food_items")
    @classmethod
    def _clean_food_items(cls, v: List[str]) -> List[str]:
        """Normalise the free-text list: trim, drop blanks, de-duplicate
        case-insensitively while preserving the vendor's original casing."""
        seen: set[str] = set()
        out: List[str] = []
        for item in v:
            item = item.strip()
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out


class VendorOnboardResponse(BaseModel):
    vendor: VendorRead
    stall: StallRead
    created: bool
    """True if this call created the records, False if they already existed
    and were updated. Lets the client show "registered" vs "already
    registered" without a second round trip."""
