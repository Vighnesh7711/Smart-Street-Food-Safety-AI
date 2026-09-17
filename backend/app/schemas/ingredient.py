"""Pydantic schemas for the ingredient knowledge base."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ScanStatus


class IngredientRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_type: str
    conditions: dict
    severity: str
    status_on_match: ScanStatus
    explanation_template: str
    is_active: bool


class IngredientSynonymRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    normalized_alias: str
    alias_type: str


class IngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_name: str
    category: str
    default_risk_level: str
    description: Optional[str] = None
    is_active: bool
    synonyms: List[IngredientSynonymRead] = []
    rules: List[IngredientRuleRead] = []
