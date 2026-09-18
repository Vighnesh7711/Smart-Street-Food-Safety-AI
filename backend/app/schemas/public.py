"""Public (unauthenticated) response schemas.

THIS MODULE IS AN ALLOW-LIST, AND THAT IS THE POINT
---------------------------------------------------
Everything here is published to anyone who scans a sticker. Nothing else is.

If the public response were instead built by taking the internal `StallRead`
and deleting fields, then adding a column to `Stall` in a later phase would
silently publish it -- the leak would happen in a commit that never mentions
the public page. With an explicit allow-list, publishing a new field requires
someone to *add* it here, which is a line a reviewer sees.

`test_public_profile.py` asserts the response key set exactly, so that
property is enforced rather than merely intended.

WHAT IS DELIBERATELY ABSENT, AND WHY
------------------------------------
Vendor name / phone / email / user_id  -- the spec forbids contact info, and
    it is the difference between "a stall" and "a named person".
stall_id, vendor_id                    -- internal identifiers. Publishing
    them would restore enumeration by the back door, defeating the whole
    reason the URL carries a random code.
Images, documents                      -- forbidden by the spec, and these are
    the fields whose accidental exposure would be most damaging.
Product name, matched ingredients      -- publishing a named brand's verdict
    from a rules engine is a claim about someone else's product. See
    PublicScanSummary.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import DISCLAIMER
from app.models.enums import ScanStatus


class PublicHygieneSummary(BaseModel):
    """Latest hygiene assessment for a stall.

    A score without its date invites a consumer to read a year-old result as
    current, which is why `assessed_at` is part of the summary rather than an
    afterthought.
    """

    score: float
    band: str
    """good / fair / poor / bad -- the same bands the vendor app uses, so a
    vendor and a consumer never see the same number described differently."""

    assessed_at: Optional[datetime] = None


class PublicScanSummary(BaseModel):
    """Latest product-label check.

    Deliberately carries the status and the date but NOT the product name.
    The verdict comes from a rules engine over a label's ingredient list;
    naming the product would publish an assertion about someone else's brand,
    which is not a claim this system is in a position to make publicly.
    """

    status: ScanStatus
    scanned_at: Optional[datetime] = None


class PublicStallProfile(BaseModel):
    """Everything the public stall page renders."""

    stall_name: str
    food_category: Optional[str] = None

    hygiene: Optional[PublicHygieneSummary] = None
    """None when the stall has never been assessed. A new stall legitimately
    has no score, and the page must say so rather than showing a zero."""

    last_scan: Optional[PublicScanSummary] = None
    """None when nothing has been scanned yet."""

    advisory_only: bool = True
    disclaimer: str = Field(default=DISCLAIMER)
    """Returned in the payload, not just rendered as page copy, so a client
    cannot present a score as a certification by simply not rendering it."""


class PublicStallLocation(BaseModel):
    """Information returned for the public consumer map."""
    stall_name: str
    latitude: float
    longitude: float
    code: str
    score: Optional[float] = None
    band: Optional[str] = None


class ConsumerReportCreate(BaseModel):
    category: str = Field(..., max_length=50)
    notes: Optional[str] = None
