"""Pydantic schemas for product scans."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ScanStatus


class MatchedIngredientRead(BaseModel):
    """One recognised ingredient, with the evidence behind the match."""

    model_config = ConfigDict(from_attributes=True)

    ingredient_id: int
    canonical_name: str
    category: str
    risk_level: str
    matched_text: Optional[str] = None
    matched_alias: Optional[str] = None
    match_confidence: float
    match_method: str
    parsed_percent: Optional[float] = None


class ImageQualityRead(BaseModel):
    ok: bool
    issues: List[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    guidance: Optional[str] = None


class ScanResultRead(BaseModel):
    """The scan result card.

    `explanation` is always the canonical English; `explanation_translated`
    is the vendor-language rendering. They are equal when the target language
    is English or when translation fell back -- which is what
    `translation_failed` distinguishes, so the UI can decide whether to show
    a fallback notice without comparing strings.
    """

    id: int
    stall_id: int
    product_name: Optional[str] = None
    status: ScanStatus

    explanation: str
    explanation_translated: str
    language_code: str
    translation_failed: bool
    recommendations: List[str] = Field(default_factory=list)

    matched_ingredients: List[MatchedIngredientRead] = Field(default_factory=list)

    ocr_confidence: Optional[float] = None
    match_confidence: Optional[float] = None
    rule_strength: Optional[float] = None
    confidence_score: Optional[float] = None

    # True only for "Needs review", where retaking the photo can change the
    # outcome. The UI keys its retake prompt off this rather than the status
    # string, so adding a status later cannot silently change the prompt.
    retake_required: bool = False

    image_quality: Optional[ImageQualityRead] = None
    ingredient_text: Optional[str] = None
    scan_image_url: Optional[str] = None
    created_at: Optional[datetime] = None


class ScanErrorRead(BaseModel):
    """Body returned when no assessment was possible at all."""

    detail: str
    retryable: bool = False
