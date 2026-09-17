"""Rule evaluation, confidence scoring, and the five-status decision.

This module is deliberately pure: no database, no network, no I/O. Given
matches and a food category it returns a verdict. That makes the precedence
rules unit-testable in isolation, which matters because they encode the
product's judgement calls.

WEIGHTED CONFIDENCE
-------------------
    overall = 0.40*ocr + 0.40*match + 0.20*rule_strength

The two 0.40 terms dominate because a verdict is only as good as the text we
read and the ingredients we recognised in it. `rule_strength` is a 0.20
term because it describes the rule that fired, not the quality of the
evidence -- a high-severity rule firing on a bad OCR read is not confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from app.core.config import settings
from app.models.enums import RiskLevel, RuleType, ScanStatus
from app.models.ingredient_rule import IngredientRule
from app.services.products.matching import IngredientMatch
from app.services.products.normalization import normalize_alias

# --- Confidence weights -------------------------------------------------
WEIGHT_OCR = 0.40
WEIGHT_MATCH = 0.40
WEIGHT_RULE = 0.20

# match_confidence blends how well each ingredient matched with how much of
# the label we actually understood.
MATCH_QUALITY_WEIGHT = 0.70
COVERAGE_WEIGHT = 0.30

# Used when no rule fires. Deliberately below 1.0: "we found nothing
# concerning" is weaker evidence than "we positively confirmed this is fine",
# because it also describes a label whose ingredient list we half-read.
NO_RULE_STRENGTH = 0.60

# OCR-confidence fallback composition, used only when the provider declines
# to report a confidence (see integrations/ocr_client.py).
FALLBACK_SHARPNESS_WEIGHT = 0.60
FALLBACK_STRUCTURE_WEIGHT = 0.40
# Token count at which the structure signal saturates.
STRUCTURE_TOKEN_TARGET = 8.0

# Below this many parsed tokens we cannot meaningfully assess a label.
MIN_TOKENS_FOR_ASSESSMENT = 2


@dataclass
class RuleOutcome:
    rule: IngredientRule
    match: IngredientMatch
    triggered: bool
    undetermined: bool = False
    """True when the rule could not be evaluated for lack of information --
    currently only a category restriction on a stall with no food category
    set. Distinct from `triggered`: we are not accusing, we are unable to
    decide."""

    reason: str = ""
    context: dict = field(default_factory=dict)
    """Template placeholders contributed by this rule."""


@dataclass
class Confidences:
    ocr: float
    match: float
    rule: float
    coverage: float

    @property
    def overall(self) -> float:
        return round(
            WEIGHT_OCR * self.ocr + WEIGHT_MATCH * self.match + WEIGHT_RULE * self.rule,
            4,
        )


def _categories_match(stall_category: Optional[str], allowed: Sequence[str]) -> bool:
    """Compare the stall's category against a rule's permitted list.

    Normalized on both sides so "sweets & confectionery" matches "Sweets &
    Confectionery" and stray punctuation does not silently change the verdict.
    """
    if not stall_category:
        return False
    normalized_stall = normalize_alias(stall_category)
    if not normalized_stall:
        return False
    for candidate in allowed:
        if normalize_alias(candidate) == normalized_stall:
            return True
    return False


def evaluate_rule(
    match: IngredientMatch, rule: IngredientRule, food_category: Optional[str]
) -> RuleOutcome:
    """Evaluate one rule against one matched ingredient."""
    ingredient_name = match.ingredient.canonical_name
    context = {
        "ingredient": ingredient_name,
        "category": food_category or "an unspecified category",
        "percent": (
            f"{match.parsed_percent:g}%" if match.parsed_percent is not None else "an undeclared amount"
        ),
    }

    if rule.rule_type == RuleType.PRESENCE:
        return RuleOutcome(
            rule=rule,
            match=match,
            triggered=True,
            reason=f"{ingredient_name} is present",
            context=context,
        )

    if rule.rule_type == RuleType.THRESHOLD:
        max_pct = rule.conditions.get("max_pct")
        context["max_pct"] = f"{max_pct:g}%" if max_pct is not None else "the permitted level"

        if max_pct is None:
            return RuleOutcome(
                rule=rule, match=match, triggered=False,
                reason="rule has no max_pct configured",
            )

        if match.parsed_percent is None:
            # The label did not declare a percentage, so we cannot show the
            # level is exceeded. Not triggering is the conservative choice:
            # accusing a vendor on an undeclared amount would be a false
            # positive. The ingredient still appears in matched_ingredients,
            # so a reviewer can see it.
            return RuleOutcome(
                rule=rule, match=match, triggered=False,
                reason="no percentage declared on the label",
                context=context,
            )

        triggered = match.parsed_percent > float(max_pct)
        return RuleOutcome(
            rule=rule,
            match=match,
            triggered=triggered,
            reason=(
                f"{match.parsed_percent:g}% exceeds the {max_pct:g}% limit"
                if triggered
                else f"{match.parsed_percent:g}% is within the {max_pct:g}% limit"
            ),
            context=context,
        )

    if rule.rule_type == RuleType.CATEGORY_RESTRICTION:
        allowed = rule.conditions.get("allowed_categories") or []
        context["allowed"] = ", ".join(allowed) if allowed else "specified categories"

        if not food_category:
            # Without knowing what the stall sells, we cannot tell whether
            # this use is permitted. Neither "fine" nor "mismatch" is honest.
            return RuleOutcome(
                rule=rule,
                match=match,
                triggered=False,
                undetermined=True,
                reason="the stall's food category is not set",
                context=context,
            )

        if _categories_match(food_category, allowed):
            return RuleOutcome(
                rule=rule, match=match, triggered=False,
                reason=f"permitted for {food_category}",
                context=context,
            )

        return RuleOutcome(
            rule=rule,
            match=match,
            triggered=True,
            reason=f"not permitted for {food_category}",
            context=context,
        )

    return RuleOutcome(
        rule=rule, match=match, triggered=False,
        reason=f"unknown rule type {rule.rule_type!r}",
    )


def evaluate_rules(
    matches: Sequence[IngredientMatch],
    food_category: Optional[str],
) -> List[RuleOutcome]:
    """Evaluate every active rule belonging to every matched ingredient."""
    outcomes: List[RuleOutcome] = []
    for match in matches:
        for rule in match.ingredient.rules:
            if not rule.is_active:
                continue
            outcomes.append(evaluate_rule(match, rule, food_category))
    return outcomes


def resolve_ocr_confidence(
    *,
    reported: Optional[float],
    sharpness_score: float,
    anchor_found: bool,
    token_count: int,
) -> float:
    """Best available estimate of OCR quality, in [0, 1].

    Google Vision frequently returns no per-word confidence for
    document_text_detection (see integrations/ocr_client.py). When that
    happens we derive an estimate from what we *can* observe: how sharp the
    image was, and how structured the text looks. Both correlate with OCR
    accuracy far better than assuming a constant.
    """
    if reported is not None:
        return max(0.0, min(1.0, float(reported)))

    structure = (
        0.5 * (1.0 if anchor_found else 0.0)
        + 0.5 * min(1.0, token_count / STRUCTURE_TOKEN_TARGET)
    )
    estimate = (
        FALLBACK_SHARPNESS_WEIGHT * max(0.0, min(1.0, sharpness_score))
        + FALLBACK_STRUCTURE_WEIGHT * structure
    )
    return round(max(0.0, min(1.0, estimate)), 4)


def compute_confidences(
    *,
    ocr_confidence: float,
    matches: Sequence[IngredientMatch],
    token_count: int,
    outcomes: Sequence[RuleOutcome],
) -> Confidences:
    """Blend the three confidence terms."""
    coverage = (
        min(1.0, len(matches) / token_count) if token_count > 0 else 0.0
    )

    if matches:
        mean_quality = sum(m.confidence for m in matches) / len(matches)
    else:
        mean_quality = 0.0

    match_confidence = (
        MATCH_QUALITY_WEIGHT * mean_quality + COVERAGE_WEIGHT * coverage
    )

    triggered = [o for o in outcomes if o.triggered]
    if triggered:
        severities = []
        for outcome in triggered:
            try:
                severities.append(RiskLevel(outcome.rule.severity).weight)
            except ValueError:
                severities.append(RiskLevel.LOW.weight)
        rule_strength = max(severities)
    else:
        rule_strength = NO_RULE_STRENGTH

    return Confidences(
        ocr=round(ocr_confidence, 4),
        match=round(match_confidence, 4),
        rule=round(rule_strength, 4),
        coverage=round(coverage, 4),
    )


@dataclass
class StatusDecision:
    status: ScanStatus
    reason: str
    retake_required: bool = False
    explanation_outcomes: List[RuleOutcome] = field(default_factory=list)
    """Outcomes whose rule fired, used to build the explanation."""


def decide_status(
    *,
    image_ok: bool,
    image_guidance: Optional[str],
    anchor_found: bool,
    token_count: int,
    matches: Sequence[IngredientMatch],
    outcomes: Sequence[RuleOutcome],
    confidences: Confidences,
) -> StatusDecision:
    """Pick one of the five statuses.

    First matching row wins. The order is the product decision, so it is
    written out as a table rather than implied by nested conditionals:

    | # | Condition                                  | Status                  | Retake |
    |---|--------------------------------------------|-------------------------|--------|
    | 1 | image quality gate failed                   | Needs review            | yes    |
    | 2 | no usable ingredient text                   | Insufficient information| no     |
    | 3a| OCR confidence below the usable floor       | Needs review            | yes    |
    | 3b| overall confidence below threshold          | Needs review            | yes    |
    | 4 | any rule -> Application mismatch            | Application mismatch    | no     |
    | 5 | any rule -> Potential concern               | Potential concern       | no     |
    | 6 | any rule undetermined (unknown category)    | Insufficient information| no     |
    | 7 | otherwise                                   | Suitable                | no     |

    Row 3a sits above 3b because the blended score can be carried by a clean
    match against badly-read text; see the comment at that check.

    Row 6 sits *below* 4 and 5 deliberately: when a definite problem and an
    undecidable one coexist, reporting the definite problem is more useful.

    Retake is offered only on rows 1 and 3. "Insufficient information" means
    we read the label and the ingredient list was not there or not usable --
    retaking the same photo would not change that, so prompting for one would
    just waste the vendor's time.
    """
    # Row 1 -- image unusable. Nothing downstream can be trusted.
    if not image_ok:
        return StatusDecision(
            status=ScanStatus.NEEDS_REVIEW,
            reason=image_guidance or "The photo was not clear enough to read.",
            retake_required=True,
        )

    # Row 2 -- no usable ingredient text.
    if not anchor_found and token_count < MIN_TOKENS_FOR_ASSESSMENT:
        return StatusDecision(
            status=ScanStatus.INSUFFICIENT_INFORMATION,
            reason=(
                "The ingredient list could not be found on this label. "
                "Make sure the ingredient panel is visible in the photo."
            ),
        )
    if token_count < MIN_TOKENS_FOR_ASSESSMENT:
        return StatusDecision(
            status=ScanStatus.INSUFFICIENT_INFORMATION,
            reason=(
                "The ingredient list was too short to assess. "
                "Check that the full ingredient panel is in the photo."
            ),
        )
    if not matches:
        return StatusDecision(
            status=ScanStatus.INSUFFICIENT_INFORMATION,
            reason=(
                "The ingredient list was read, but none of the ingredients "
                "are in our reference list yet. This label has not been assessed."
            ),
        )

    overall = confidences.overall

    # Row 3a -- the text itself is untrustworthy.
    #
    # Checked separately from the blended score because the blend can be
    # carried by a clean-looking match: a misread token ("Palm Oil" from
    # something else entirely) matches a real ingredient exactly, so
    # match_confidence and rule_strength both read as strong evidence for a
    # verdict that rests on text we could barely read. Garbage in, confident
    # verdict out -- which is precisely the failure a vendor cannot detect.
    if confidences.ocr < settings.SCAN_MIN_USABLE_CONFIDENCE:
        return StatusDecision(
            status=ScanStatus.NEEDS_REVIEW,
            reason=(
                "We could not read this label clearly enough to trust the "
                "result. Please retake the photo in good light, holding the "
                "phone steady with the ingredient list filling the frame."
            ),
            retake_required=True,
        )

    # Row 3b -- readable, but not confidently.
    if overall < settings.SCAN_REVIEW_THRESHOLD:
        return StatusDecision(
            status=ScanStatus.NEEDS_REVIEW,
            reason=(
                "We could not read this label confidently enough to give a "
                "reliable result. Please retake the photo in good light, "
                "filling the frame with the ingredient list."
            ),
            retake_required=True,
        )

    triggered = [o for o in outcomes if o.triggered]

    # Row 4 -- category restriction violated.
    mismatch = [
        o
        for o in triggered
        if o.rule.status_on_match == ScanStatus.APPLICATION_MISMATCH.value
    ]
    if mismatch:
        names = ", ".join(sorted({o.match.ingredient.canonical_name for o in mismatch}))
        return StatusDecision(
            status=ScanStatus.APPLICATION_MISMATCH,
            reason=f"Not intended for this type of food: {names}.",
            explanation_outcomes=mismatch,
        )

    # Row 5 -- a concern was raised.
    concerns = [
        o
        for o in triggered
        if o.rule.status_on_match == ScanStatus.POTENTIAL_CONCERN.value
    ]
    if concerns:
        names = ", ".join(sorted({o.match.ingredient.canonical_name for o in concerns}))
        return StatusDecision(
            status=ScanStatus.POTENTIAL_CONCERN,
            reason=f"Worth knowing about: {names}.",
            explanation_outcomes=concerns,
        )

    # Row 6 -- nothing fired, but something could not be evaluated.
    undetermined = [o for o in outcomes if o.undetermined]
    if undetermined:
        names = ", ".join(
            sorted({o.match.ingredient.canonical_name for o in undetermined})
        )
        return StatusDecision(
            status=ScanStatus.INSUFFICIENT_INFORMATION,
            reason=(
                f"Cannot confirm this is suitable: {names} is permitted only "
                "in certain food categories, and your stall's category is not "
                "set. Add it in your stall profile to get a definite result."
            ),
        )

    return StatusDecision(
        status=ScanStatus.SUITABLE,
        reason="No concerns found among the ingredients we recognised.",
    )
