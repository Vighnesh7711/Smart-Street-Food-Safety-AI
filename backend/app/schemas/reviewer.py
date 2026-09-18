"""Schemas for the reviewer dashboard.

These describe data about vendors and their stalls, so unlike the public
schemas they deliberately DO include identifying detail -- the whole point of
this surface is that a reviewer can see who and where. Access is what
protects it, not field omission.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import FlagStatus, ReviewSort, ScanStatus, ViewCategory


class VendorRowRead(BaseModel):
    """One row of the vendors table."""

    stall_id: int
    stall_name: str
    food_category: Optional[str] = None
    vendor_id: int
    vendor_name: Optional[str] = None

    latest_score: Optional[float] = None
    latest_score_at: Optional[datetime] = None
    band: Optional[str] = None
    """good / fair / poor / bad, or None when the stall has never been
    assessed. None is NOT the same as "bad" -- an unassessed stall must not
    appear as the worst performer."""

    latest_scan_status: Optional[ScanStatus] = None
    latest_scan_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None

    has_open_flag: bool = False
    open_flag_count: int = 0


class VendorListResponse(BaseModel):
    items: List[VendorRowRead] = Field(default_factory=list)
    total: int
    """Unpaginated count for the current filters, so the table can show
    "showing 1-50 of 240" rather than leaving the reviewer guessing."""

    skip: int
    limit: int


class BandCounts(BaseModel):
    good: int = 0
    fair: int = 0
    poor: int = 0
    bad: int = 0
    none: int = 0
    """Stalls with no assessment. Kept separate from `bad` for the same
    reason the band is nullable."""


class ReviewerSummaryRead(BaseModel):
    total_stalls: int
    assessed_stalls: int
    flagged_stalls: int
    average_score: Optional[float] = None
    checks_last_7_days: int
    bands: BandCounts


class HygieneHistoryPoint(BaseModel):
    check_id: int
    score: float
    visual_score: float
    checklist_score: Optional[float] = None
    band: str
    formula_version: str
    assessed_at: Optional[datetime] = None


class ScanHistoryRow(BaseModel):
    scan_id: int
    status: ScanStatus
    language_code: str
    translation_failed: bool
    confidence_score: Optional[float] = None
    ocr_confidence: Optional[float] = None
    ingredient_count: int = 0
    scanned_at: Optional[datetime] = None


class DetectedIndicatorRead(BaseModel):
    code: str
    display_name: str
    """Resolved from the indicator catalog server-side, so the gallery does
    not need a second request just to label what it is showing."""

    view: str
    confidence: float
    penalty: float
    raw_labels: List[str] = Field(default_factory=list)
    bbox: Optional[List[int]] = None
    """[x1, y1, x2, y2] in the coordinate space recorded by `box_space`."""


class StallImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_id: int
    view_category: ViewCategory
    view_display_name: str
    image_url: str
    detected_at: Optional[datetime] = None

    detections: List[DetectedIndicatorRead] = Field(default_factory=list)

    box_space: Optional[Dict[str, float]] = None
    """The pixel dimensions the bounding boxes are expressed in, recorded by
    the CV provider. The overlay divides by these to get percentages, so it
    works at any display size and does not have to reimplement the
    detector's downscale rule."""

    quality_issues: List[str] = Field(default_factory=list)


class VendorDetailRead(BaseModel):
    stall_id: int
    stall_name: str
    food_category: Optional[str] = None
    vendor_id: int
    vendor_name: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None

    current_score: Optional[float] = None
    current_band: Optional[str] = None
    score_delta: Optional[float] = None
    """Change since the previous assessment. None when there is no previous
    one -- showing "+63" for a first-ever check would be meaningless."""

    hygiene_history: List[HygieneHistoryPoint] = Field(default_factory=list)
    scan_history: List[ScanHistoryRow] = Field(default_factory=list)
    images: List[StallImageRead] = Field(default_factory=list)
    open_flags: List["FlagRead"] = Field(default_factory=list)


class FlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stall_id: int
    stall_name: Optional[str] = None
    reason: str
    status: FlagStatus
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


class FlagCreate(BaseModel):
    """Raising a flag.

    The reason is required and non-blank: a flag with no reason is not
    actionable by whoever picks it up later, which defeats the point of
    recording it at all.
    """

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Please give a short reason (at least 3 characters).")
        return cleaned


class FlagResolve(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


class FlagListResponse(BaseModel):
    items: List[FlagRead] = Field(default_factory=list)
    total: int
    skip: int
    limit: int


class AuditLogRead(BaseModel):
    id: int
    action: str
    actor_id: int
    actor_name: Optional[str] = None
    target_type: str
    target_id: int
    details: Optional[Dict] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogRead] = Field(default_factory=list)
    total: int
    skip: int
    limit: int


class AnalyticsAggregateRead(BaseModel):
    date: datetime
    total_stalls: int
    assessed_stalls: int
    flagged_stalls: int
    average_score: Optional[float] = None
    scans_performed: int
    flags_created: int
    flags_resolved: int
    checks_performed: int


class AnalyticsListResponse(BaseModel):
    items: List[AnalyticsAggregateRead] = Field(default_factory=list)


# Resolve the forward reference in VendorDetailRead.
VendorDetailRead.model_rebuild()
