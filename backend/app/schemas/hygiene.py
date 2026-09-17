"""Pydantic schemas for hygiene checks."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CheckStatus, ViewCategory


class ChecklistItemRead(BaseModel):
    code: str
    label: str
    help_text: str


class ChecklistAnswerRow(BaseModel):
    """One checklist item with the vendor's answer and whether it counted."""

    code: str
    label: str
    help_text: str
    answered: bool
    answer: Optional[bool] = None
    satisfied: bool


class ChecklistSubmit(BaseModel):
    answers: Dict[str, bool] = Field(default_factory=dict)


class HygieneImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    view_category: ViewCategory
    view_display_name: str
    image_url: str
    quality_ok: bool = True
    quality_issues: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class IndicatorFindingRead(BaseModel):
    code: str
    display_name: str
    view: str
    severity: str
    penalty: float
    confidence: float
    detection_count: int
    raw_labels: List[str] = Field(default_factory=list)


class HygieneScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    visual_score: float
    checklist_score: Optional[float] = None
    final_score: float
    band: str
    formula_version: str
    weights: Dict[str, float] = Field(default_factory=dict)
    computed_at: Optional[datetime] = None


class CoverageRead(BaseModel):
    ok: bool
    present: List[ViewCategory] = Field(default_factory=list)
    missing: List[ViewCategory] = Field(default_factory=list)
    message: str = ""
    """Names the specific views still needed, e.g. "Still needed: the storage
    area and the waste area." Empty once complete."""

    next_view: Optional[ViewCategory] = None
    """Which view the guided capture flow should ask for next."""

    progress: float = 0.0
    """Fraction of the four required views collected, for the progress bar."""


class HygieneCheckRead(BaseModel):
    """Full check detail: coverage, images, findings, and score."""

    id: int
    stall_id: int
    status: CheckStatus
    coverage: CoverageRead
    images: List[HygieneImageRead] = Field(default_factory=list)
    score: Optional[HygieneScoreRead] = None
    indicators_found: List[IndicatorFindingRead] = Field(default_factory=list)
    checklist: List[ChecklistAnswerRow] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None

    # Always true, and stated in the payload rather than only in the UI, so
    # an API consumer cannot present a score as an official certification.
    advisory_only: bool = True
    disclaimer: str = (
        "AI-assisted assessment, not an official certification. "
        "It is a guide to help you improve, not a licence or a clearance."
    )


class HygieneCheckSummary(BaseModel):
    """Compact row for the history list."""

    id: int
    stall_id: int
    status: CheckStatus
    final_score: Optional[float] = None
    band: Optional[str] = None
    indicator_count: int = 0
    coverage_ok: bool = False
    missing_views: List[ViewCategory] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None
    created_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None


class IndicatorCatalogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str
    description: Optional[str] = None
    default_severity: str
    view_penalties: Dict[str, int] = Field(default_factory=dict)


class HygieneConfigRead(BaseModel):
    """Everything the mobile capture flow needs to render itself."""

    required_views: List[dict]
    checklist_items: List[ChecklistItemRead]
    disclaimer: str
