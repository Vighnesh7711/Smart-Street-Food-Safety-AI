"""Rule evaluation, confidence weighting, and status precedence.

status_engine is pure, so these tests build detached ORM objects rather than
touching a database. That keeps the precedence table -- which is the actual
product decision -- testable without any infrastructure.
"""

import pytest

from app.core.config import settings
from app.models.enums import MatchMethod, RiskLevel, RuleType, ScanStatus
from app.models.ingredient import Ingredient
from app.models.ingredient_rule import IngredientRule
from app.services.products.matching import IngredientMatch
from app.services.products.status_engine import (
    Confidences,
    compute_confidences,
    decide_status,
    evaluate_rule,
    evaluate_rules,
    resolve_ocr_confidence,
)


def make_rule(
    rule_type: RuleType = RuleType.PRESENCE,
    status_on_match: ScanStatus = ScanStatus.POTENTIAL_CONCERN,
    severity: RiskLevel = RiskLevel.MODERATE,
    conditions: dict | None = None,
    template: str = "{ingredient} triggered a rule.",
    is_active: bool = True,
) -> IngredientRule:
    return IngredientRule(
        rule_type=rule_type.value,
        conditions=conditions or {},
        severity=severity.value,
        status_on_match=status_on_match.value,
        explanation_template=template,
        is_active=is_active,
    )


def make_ingredient(
    name: str = "Palm Oil",
    risk: RiskLevel = RiskLevel.MODERATE,
    rules: list | None = None,
) -> Ingredient:
    ingredient = Ingredient(
        canonical_name=name,
        category="Fat/Oil",
        default_risk_level=risk.value,
        is_active=True,
    )
    ingredient.rules = rules or []
    return ingredient


def make_match(
    ingredient: Ingredient | None = None,
    confidence: float = 1.0,
    percent: float | None = None,
) -> IngredientMatch:
    return IngredientMatch(
        ingredient=ingredient or make_ingredient(),
        matched_text="palm oil",
        matched_alias="palm oil",
        confidence=confidence,
        method=MatchMethod.EXACT,
        position=0,
        parsed_percent=percent,
    )


def make_confidences(ocr=0.9, match=0.9, rule=0.6) -> Confidences:
    return Confidences(ocr=ocr, match=match, rule=rule, coverage=0.8)


class TestPresenceRule:
    def test_always_triggers(self):
        outcome = evaluate_rule(make_match(), make_rule(), "Snacks")
        assert outcome.triggered
        assert not outcome.undetermined

    def test_inactive_rule_is_skipped(self):
        match = make_match(make_ingredient(rules=[make_rule(is_active=False)]))
        assert evaluate_rules([match], "Snacks") == []


class TestThresholdRule:
    def test_triggers_above_limit(self):
        rule = make_rule(
            RuleType.THRESHOLD, conditions={"max_pct": 2.0}
        )
        outcome = evaluate_rule(make_match(percent=5.0), rule, "Snacks")
        assert outcome.triggered

    def test_does_not_trigger_below_limit(self):
        rule = make_rule(RuleType.THRESHOLD, conditions={"max_pct": 2.0})
        outcome = evaluate_rule(make_match(percent=1.0), rule, "Snacks")
        assert not outcome.triggered

    def test_undeclared_percentage_does_not_trigger(self):
        """Conservative on purpose: accusing a vendor of exceeding a limit on
        an amount the label never declared would be a false positive."""
        rule = make_rule(RuleType.THRESHOLD, conditions={"max_pct": 2.0})
        outcome = evaluate_rule(make_match(percent=None), rule, "Snacks")
        assert not outcome.triggered
        assert not outcome.undetermined
        assert "no percentage" in outcome.reason

    def test_missing_max_pct_does_not_trigger(self):
        rule = make_rule(RuleType.THRESHOLD, conditions={})
        outcome = evaluate_rule(make_match(percent=99.0), rule, "Snacks")
        assert not outcome.triggered


class TestCategoryRestriction:
    rule = make_rule(
        RuleType.CATEGORY_RESTRICTION,
        status_on_match=ScanStatus.APPLICATION_MISMATCH,
        conditions={"allowed_categories": ["Beverages", "Snacks"]},
    )

    def test_allowed_category_does_not_trigger(self):
        outcome = evaluate_rule(make_match(), self.rule, "Beverages")
        assert not outcome.triggered
        assert not outcome.undetermined

    def test_match_is_case_and_punctuation_insensitive(self):
        outcome = evaluate_rule(make_match(), self.rule, "  beverages  ")
        assert not outcome.triggered

    def test_disallowed_category_triggers(self):
        outcome = evaluate_rule(make_match(), self.rule, "Dairy")
        assert outcome.triggered
        assert "Dairy" in outcome.reason

    def test_unknown_category_is_undetermined_not_triggered(self):
        """Without knowing what the stall sells we can neither clear nor
        accuse -- so the outcome is explicitly "undetermined"."""
        outcome = evaluate_rule(make_match(), self.rule, None)
        assert not outcome.triggered
        assert outcome.undetermined

    def test_empty_category_is_undetermined(self):
        outcome = evaluate_rule(make_match(), self.rule, "")
        assert outcome.undetermined


class TestConfidenceWeighting:
    def test_weights_sum_to_one(self):
        from app.services.products.status_engine import (
            WEIGHT_MATCH,
            WEIGHT_OCR,
            WEIGHT_RULE,
        )

        assert WEIGHT_OCR + WEIGHT_MATCH + WEIGHT_RULE == pytest.approx(1.0)

    def test_overall_is_the_documented_blend(self):
        c = Confidences(ocr=1.0, match=0.5, rule=0.0, coverage=0.0)
        assert c.overall == pytest.approx(0.40 * 1.0 + 0.40 * 0.5 + 0.20 * 0.0)

    def test_no_rule_triggered_uses_neutral_strength(self):
        match = make_match(confidence=1.0)
        confidences = compute_confidences(
            ocr_confidence=0.9, matches=[match], token_count=1, outcomes=[]
        )
        assert confidences.rule == pytest.approx(0.60)

    def test_highest_severity_wins(self):
        low = make_ingredient("A", rules=[make_rule(severity=RiskLevel.LOW)])
        high = make_ingredient("B", rules=[make_rule(severity=RiskLevel.HIGH)])
        matches = [make_match(low), make_match(high)]
        outcomes = evaluate_rules(matches, "Snacks")
        confidences = compute_confidences(
            ocr_confidence=0.9, matches=matches, token_count=2, outcomes=outcomes
        )
        assert confidences.rule == pytest.approx(RiskLevel.HIGH.weight)

    def test_coverage_reflects_unmatched_tokens(self):
        match = make_match(confidence=1.0)
        full = compute_confidences(
            ocr_confidence=0.9, matches=[match], token_count=1, outcomes=[]
        )
        partial = compute_confidences(
            ocr_confidence=0.9, matches=[match], token_count=10, outcomes=[]
        )
        assert full.coverage == pytest.approx(1.0)
        assert partial.coverage == pytest.approx(0.1)
        assert partial.match < full.match


class TestOcrConfidenceFallback:
    def test_reported_value_is_used_as_is(self):
        assert resolve_ocr_confidence(
            reported=0.77, sharpness_score=0.1, anchor_found=False, token_count=0
        ) == pytest.approx(0.77)

    def test_missing_report_falls_back_to_observable_signals(self):
        """Vision often returns no confidence at all; returning 0.0 would
        drive every scan to "Needs review"."""
        estimate = resolve_ocr_confidence(
            reported=None, sharpness_score=1.0, anchor_found=True, token_count=8
        )
        assert estimate > 0.5

    def test_poor_image_scores_lower_than_good_image(self):
        poor = resolve_ocr_confidence(
            reported=None, sharpness_score=0.0, anchor_found=False, token_count=1
        )
        good = resolve_ocr_confidence(
            reported=None, sharpness_score=1.0, anchor_found=True, token_count=8
        )
        assert poor < good

    def test_estimate_is_bounded(self):
        assert 0.0 <= resolve_ocr_confidence(
            reported=None, sharpness_score=5.0, anchor_found=True, token_count=99
        ) <= 1.0


class TestStatusPrecedence:
    """One test per row of the precedence table in decide_status."""

    base = dict(
        image_ok=True,
        image_guidance=None,
        anchor_found=True,
        token_count=5,
        matches=[make_match()],
        outcomes=[],
    )

    def test_row1_image_failure_is_needs_review_with_retake(self):
        decision = decide_status(
            **{**self.base, "image_ok": False,
               "image_guidance": "The photo is blurry.", "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.NEEDS_REVIEW
        assert decision.retake_required is True
        assert "blurry" in decision.reason

    def test_row2_no_ingredient_text_is_insufficient(self):
        decision = decide_status(
            **{**self.base, "anchor_found": False, "token_count": 0,
               "matches": [], "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.INSUFFICIENT_INFORMATION
        # Retaking the same photo would not help, so no retake prompt.
        assert decision.retake_required is False

    def test_row2_too_few_tokens(self):
        decision = decide_status(
            **{**self.base, "token_count": 1, "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.INSUFFICIENT_INFORMATION

    def test_row2_no_matches_at_all(self):
        decision = decide_status(
            **{**self.base, "matches": [], "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.INSUFFICIENT_INFORMATION
        assert "reference list" in decision.reason

    def test_row3_low_confidence_is_needs_review_with_retake(self):
        decision = decide_status(
            **{**self.base,
               "confidences": make_confidences(ocr=0.1, match=0.1, rule=0.0)}
        )
        assert decision.status == ScanStatus.NEEDS_REVIEW
        assert decision.retake_required is True

    def test_row3a_unreadable_text_blocks_a_confident_verdict(self):
        """A clean match against badly-read text must not produce certainty.

        A misread token can match a real ingredient exactly, so match and
        rule terms both look strong while the verdict rests on text we could
        barely read. This is the failure a vendor cannot detect for
        themselves, so OCR confidence gates independently of the blend.
        """
        matches = [make_match(make_ingredient("Palm Oil", rules=[make_rule()]))]
        strong_but_illegible = Confidences(
            ocr=settings.SCAN_MIN_USABLE_CONFIDENCE - 0.01,
            match=1.0,
            rule=RiskLevel.HIGH.weight,
            coverage=1.0,
        )
        # The blend alone would clear the threshold...
        assert strong_but_illegible.overall > settings.SCAN_REVIEW_THRESHOLD

        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, "Snacks"),
               "confidences": strong_but_illegible}
        )
        # ...but the scan is still sent back for a retake.
        assert decision.status == ScanStatus.NEEDS_REVIEW
        assert decision.retake_required is True

    def test_row3b_low_blended_confidence_is_needs_review(self):
        matches = [make_match(make_ingredient("Palm Oil", rules=[make_rule()]))]
        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, "Snacks"),
               "confidences": make_confidences(ocr=0.3, match=0.1, rule=0.1)}
        )
        assert decision.status == ScanStatus.NEEDS_REVIEW

    def test_row4_mismatch_beats_concern(self):
        mismatch = make_ingredient(
            "Tartrazine",
            rules=[make_rule(
                RuleType.CATEGORY_RESTRICTION,
                status_on_match=ScanStatus.APPLICATION_MISMATCH,
                conditions={"allowed_categories": ["Beverages"]},
            )],
        )
        concern = make_ingredient("Palm Oil", rules=[make_rule()])
        matches = [make_match(mismatch), make_match(concern)]
        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, "Dairy"),
               "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.APPLICATION_MISMATCH

    def test_row5_concern(self):
        matches = [make_match(make_ingredient("Palm Oil", rules=[make_rule()]))]
        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, "Snacks"),
               "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.POTENTIAL_CONCERN

    def test_row6_undetermined_is_insufficient(self):
        restricted = make_ingredient(
            "Sodium Benzoate",
            rules=[make_rule(
                RuleType.CATEGORY_RESTRICTION,
                status_on_match=ScanStatus.APPLICATION_MISMATCH,
                conditions={"allowed_categories": ["Beverages"]},
            )],
        )
        matches = [make_match(restricted)]
        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, None),
               "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.INSUFFICIENT_INFORMATION
        assert "category is not set" in decision.reason
        assert decision.retake_required is False

    def test_row6_does_not_override_a_definite_concern(self):
        """When a definite problem and an undecidable one coexist, report the
        definite problem."""
        restricted = make_ingredient(
            "Sodium Benzoate",
            rules=[make_rule(
                RuleType.CATEGORY_RESTRICTION,
                status_on_match=ScanStatus.APPLICATION_MISMATCH,
                conditions={"allowed_categories": ["Beverages"]},
            )],
        )
        concern = make_ingredient("Palm Oil", rules=[make_rule()])
        matches = [make_match(restricted), make_match(concern)]
        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, None),
               "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.POTENTIAL_CONCERN

    def test_row7_suitable_with_rule_free_ingredients(self):
        matches = [make_match(make_ingredient("Turmeric", risk=RiskLevel.LOW))]
        decision = decide_status(
            **{**self.base, "matches": matches,
               "outcomes": evaluate_rules(matches, "Snacks"),
               "confidences": make_confidences()}
        )
        assert decision.status == ScanStatus.SUITABLE
        assert decision.retake_required is False

    def test_review_threshold_boundary(self):
        """The review threshold is a setting, and it is the *blended* score
        that must cross it -- not any single term.

        OCR confidence is held above SCAN_MIN_USABLE_CONFIDENCE here so this
        exercises row 3b rather than the hard unreadable-text gate (3a).
        """
        threshold = settings.SCAN_REVIEW_THRESHOLD
        usable_ocr = settings.SCAN_MIN_USABLE_CONFIDENCE + 0.05

        # Weak across the board -> blended score below the threshold.
        below = Confidences(
            ocr=usable_ocr, match=0.1, rule=0.1, coverage=0.1
        )
        assert below.overall < threshold
        assert decide_status(**{**self.base, "confidences": below}).status == (
            ScanStatus.NEEDS_REVIEW
        )

        # Same OCR weakness, but the matches are solid -> the blend clears
        # the threshold, because match quality carries an equal 0.40 weight.
        well_matched = Confidences(
            ocr=usable_ocr, match=1.0, rule=1.0, coverage=1.0
        )
        assert well_matched.overall >= threshold
        assert decide_status(
            **{**self.base, "confidences": well_matched}
        ).status != ScanStatus.NEEDS_REVIEW
