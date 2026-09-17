"""Resolve parsed label tokens to knowledge-base ingredients.

Three stages, cheapest first, each recording *how* it matched so the verdict
can be explained and disputed:

  1. exact     -- normalized token equals a normalized alias
  2. containment -- the token contains a multiword alias ("refined wheat
                    flour maida" contains "refined wheat flour")
  3. fuzzy     -- edit-distance recovery of OCR typos ("sodium benzoatc")

Containment is deliberately whole-word rather than substring. Matching
"sodium" against the alias "sodium benzoate" via substring would flag every
label containing plain sodium, which is a false accusation against a vendor
-- exactly the failure mode that makes a tool like this untrustworthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import MatchMethod
from app.models.ingredient import Ingredient, IngredientSynonym
from app.services.products.normalization import ParsedToken, normalize_alias

# Fuzzy matching is only attempted for tokens at least this long. Short
# tokens have too many near-neighbours ("salt"/"malt") for edit distance to
# be meaningful.
_MIN_FUZZY_TOKEN_LENGTH = 6

# Confidence assigned per match method. These feed the match-confidence term
# of the overall score; see status_engine.py.
_CONFIDENCE = {
    MatchMethod.EXACT: 1.0,
    MatchMethod.E_NUMBER: 1.0,
    MatchMethod.ALIAS: 0.92,
    MatchMethod.FUZZY: 0.0,  # computed from the similarity score
}

_FUZZY_CEILING = 0.9
"""A fuzzy match can never be as trustworthy as an exact one, so its
confidence is capped below 1.0 regardless of similarity."""


@dataclass
class IngredientMatch:
    ingredient: Ingredient
    matched_text: str
    matched_alias: str
    confidence: float
    method: MatchMethod
    position: int
    parsed_percent: Optional[float] = None


class KnowledgeBase:
    """In-memory lookup index built from the ingredients tables.

    Built once per scan. At the seeded size (~130 aliases) this is cheaper
    than a DB round trip per token; if the knowledge base grows by orders of
    magnitude this should move to a cached, explicitly invalidated index.
    """

    def __init__(self, ingredients: Sequence[Ingredient]):
        self.ingredients = list(ingredients)
        self.by_alias: Dict[str, Ingredient] = {}
        self.alias_original: Dict[str, str] = {}
        self.by_id: Dict[int, Ingredient] = {}

        for ingredient in self.ingredients:
            self.by_id[ingredient.id] = ingredient
            self._index(normalize_alias(ingredient.canonical_name), ingredient,
                        ingredient.canonical_name)
            for synonym in ingredient.synonyms:
                self._index(
                    synonym.normalized_alias or normalize_alias(synonym.alias),
                    ingredient,
                    synonym.alias,
                )

        # Longest aliases first, so containment prefers "sodium benzoate"
        # over a shorter alias that also happens to be present.
        self.aliases_by_length: List[str] = sorted(
            self.by_alias.keys(), key=len, reverse=True
        )

    def _index(self, normalized: str, ingredient: Ingredient, original: str) -> None:
        if not normalized:
            return
        # First writer wins: the canonical name is indexed before synonyms,
        # so a genuine collision cannot silently rebind an ingredient.
        if normalized not in self.by_alias:
            self.by_alias[normalized] = ingredient
            self.alias_original[normalized] = original

    def __len__(self) -> int:
        return len(self.ingredients)


def load_knowledge_base(db: Session) -> KnowledgeBase:
    """Load all active ingredients with their synonyms."""
    ingredients = (
        db.query(Ingredient)
        .filter(Ingredient.is_active.is_(True))
        .order_by(Ingredient.id)
        .all()
    )
    return KnowledgeBase(ingredients)


def _contains_phrase(haystack: str, needle: str) -> bool:
    """Whole-word containment on already-normalized strings.

    Both sides are space-separated word sequences after normalization, so
    padding with spaces gives exact word boundaries without a regex. A regex
    with `\\b` would fail on Devanagari for the reason documented in
    normalization.py.
    """
    if not needle or not haystack:
        return False
    return f" {needle} " in f" {haystack} "


def _match_token(token: ParsedToken, kb: KnowledgeBase) -> Optional[IngredientMatch]:
    if not token.normalized:
        return None

    # --- Stage 1: exact lookup in the alias index ---
    ingredient = kb.by_alias.get(token.normalized)
    if ingredient is not None:
        # The index holds canonical names and synonyms alike, so "did the
        # label literally say Palm Oil, or a trade name like Ajinomoto?"
        # has to be recovered by comparing against the canonical form.
        # Recording which one hit is what lets a reviewer verify a verdict
        # against the physical packet.
        if token.is_e_number:
            method = MatchMethod.E_NUMBER
        elif normalize_alias(ingredient.canonical_name) == token.normalized:
            method = MatchMethod.EXACT
        else:
            method = MatchMethod.ALIAS
        return IngredientMatch(
            ingredient=ingredient,
            matched_text=token.raw,
            matched_alias=kb.alias_original.get(token.normalized, token.normalized),
            confidence=_CONFIDENCE[method],
            method=method,
            position=token.position,
            parsed_percent=token.percent,
        )

    # --- Stage 2: whole-word containment of a longer alias ---
    for alias in kb.aliases_by_length:
        # An alias shorter than the token can still be contained; one longer
        # than the token cannot.
        if len(alias) > len(token.normalized) + 1:
            continue
        if _contains_phrase(token.normalized, alias):
            return IngredientMatch(
                ingredient=kb.by_alias[alias],
                matched_text=token.raw,
                matched_alias=kb.alias_original.get(alias, alias),
                confidence=_CONFIDENCE[MatchMethod.ALIAS],
                method=MatchMethod.ALIAS,
                position=token.position,
                parsed_percent=token.percent,
            )

    # --- Stage 3: fuzzy OCR-typo recovery ---
    if len(token.normalized) < _MIN_FUZZY_TOKEN_LENGTH:
        return None

    result = process.extractOne(
        token.normalized,
        kb.aliases_by_length,
        scorer=fuzz.ratio,
        score_cutoff=settings.SCAN_FUZZY_MATCH_THRESHOLD,
    )
    if result is None:
        return None

    alias, score, _ = result
    return IngredientMatch(
        ingredient=kb.by_alias[alias],
        matched_text=token.raw,
        matched_alias=kb.alias_original.get(alias, alias),
        confidence=(score / 100.0) * _FUZZY_CEILING,
        method=MatchMethod.FUZZY,
        position=token.position,
        parsed_percent=token.percent,
    )


def match_tokens(
    tokens: Iterable[ParsedToken], kb: KnowledgeBase
) -> List[IngredientMatch]:
    """Match every token, keeping the strongest match per ingredient."""
    best: Dict[int, IngredientMatch] = {}

    for token in tokens:
        match = _match_token(token, kb)
        if match is None:
            continue
        existing = best.get(match.ingredient.id)
        if existing is None or match.confidence > existing.confidence:
            best[match.ingredient.id] = match

    # Preserve label order: the position field lets the UI highlight matches
    # in the order they appear on the packet.
    return sorted(best.values(), key=lambda m: m.position)
