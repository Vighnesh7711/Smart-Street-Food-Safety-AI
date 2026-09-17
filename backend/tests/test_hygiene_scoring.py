"""The hygiene score formula and checklist scoring."""

import pytest

from app.core.config import settings
from app.models.enums import RiskLevel, ViewCategory
from app.services.hygiene.checklist import (
    TOTAL_ITEMS,
    describe_checklist,
    item_codes,
    score_checklist,
)
from app.services.hygiene.indicators import IndicatorFinding
from app.services.hygiene.scoring import (
    ScoringConfigError,
    compute_final_score,
    compute_score,
    compute_visual_score,
    score_band,
    validate_weights,
)


def finding(penalty: float = 10.0, view: str = ViewCategory.PREP_AREA.value) -> IndicatorFinding:
    return IndicatorFinding(
        code="visible_waste",
        display_name="Visible waste or litter",
        view=view,
        severity=RiskLevel.HIGH.value,
        penalty=penalty,
        confidence=1.0,
    )


class TestWeights:
    def test_default_weights_are_visual_dominant(self):
        assert settings.HYGIENE_VISUAL_WEIGHT == pytest.approx(0.70)
        assert settings.HYGIENE_CHECKLIST_WEIGHT == pytest.approx(0.30)

    def test_default_weights_validate(self):
        validate_weights()

    def test_weights_must_sum_to_one(self, monkeypatch):
        monkeypatch.setattr(settings, "HYGIENE_VISUAL_WEIGHT", 0.9)
        monkeypatch.setattr(settings, "HYGIENE_CHECKLIST_WEIGHT", 0.9)
        with pytest.raises(ScoringConfigError):
            validate_weights()

    def test_weights_must_be_in_range(self, monkeypatch):
        monkeypatch.setattr(settings, "HYGIENE_VISUAL_WEIGHT", 1.5)
        monkeypatch.setattr(settings, "HYGIENE_CHECKLIST_WEIGHT", -0.5)
        with pytest.raises(ScoringConfigError):
            validate_weights()


class TestVisualScore:
    def test_no_findings_is_a_perfect_score(self):
        score, breakdown = compute_visual_score([])
        assert score == 100.0
        assert breakdown["total_penalty"] == 0.0

    def test_penalties_are_deducted(self):
        score, _ = compute_visual_score([finding(18.0), finding(12.0)])
        assert score == pytest.approx(70.0)

    def test_score_is_clamped_at_zero(self):
        """A very dirty stall can exceed 100 points of penalty; the score must
        not go negative."""
        score, breakdown = compute_visual_score([finding(80.0), finding(80.0)])
        assert score == 0.0
        assert breakdown["clamped"] is True
        assert breakdown["total_penalty"] == pytest.approx(160.0)

    def test_clamped_flag_distinguishes_exactly_zero(self):
        _, exactly_zero = compute_visual_score([finding(100.0)])
        assert exactly_zero["clamped"] is False

    def test_breakdown_groups_penalties_by_view(self):
        _, breakdown = compute_visual_score(
            [
                finding(10.0, ViewCategory.PREP_AREA.value),
                finding(5.0, ViewCategory.PREP_AREA.value),
                finding(4.0, ViewCategory.STORAGE_AREA.value),
            ]
        )
        assert breakdown["penalty_by_view"][ViewCategory.PREP_AREA.value] == 15.0
        assert breakdown["penalty_by_view"][ViewCategory.STORAGE_AREA.value] == 4.0

    def test_zero_penalty_findings_do_not_lower_the_score(self):
        """Waste in the waste area is recorded as a finding but costs nothing."""
        score, breakdown = compute_visual_score([finding(0.0, ViewCategory.WASTE_AREA.value)])
        assert score == 100.0
        assert breakdown["finding_count"] == 1

    def test_breakdown_carries_every_finding(self):
        _, breakdown = compute_visual_score([finding(3.0), finding(4.0)])
        assert len(breakdown["findings"]) == 2


class TestFinalScore:
    def test_blend_matches_the_documented_formula(self):
        assert compute_final_score(50.0, 100.0) == pytest.approx(0.7 * 50 + 0.3 * 100)

    def test_missing_checklist_uses_visual_alone(self):
        """Not imputed: inventing a checklist score would make a skipped
        checklist indistinguishable from a completed one."""
        assert compute_final_score(72.0, None) == pytest.approx(72.0)

    def test_visual_alone_is_still_clamped(self):
        assert compute_final_score(140.0, None) == 100.0

    def test_checklist_cannot_rescue_a_terrible_visual_score(self):
        """The gaming-resistance property the weighting exists for."""
        score = compute_final_score(0.0, 100.0)
        assert score == pytest.approx(30.0)

    def test_score_is_clamped_at_100(self):
        assert compute_final_score(100.0, 100.0) == 100.0


class TestComputeScore:
    def test_full_result_shape(self):
        result = compute_score([finding(18.0)], checklist_score=83.33)
        assert result.visual_score == pytest.approx(82.0)
        assert result.checklist_score == pytest.approx(83.33)
        assert result.final_score == pytest.approx(0.7 * 82.0 + 0.3 * 83.33, abs=0.01)
        assert result.formula_version
        assert result.weights == {"visual": 0.70, "checklist": 0.30}

    def test_breakdown_records_whether_the_checklist_applied(self):
        applied = compute_score([], checklist_score=50.0)
        skipped = compute_score([], checklist_score=None)
        assert applied.breakdown["checklist_applied"] is True
        assert skipped.breakdown["checklist_applied"] is False

    def test_formula_version_is_stable(self):
        assert compute_score([], None).formula_version == "v1"


class TestScoreBand:
    @pytest.mark.parametrize(
        "score,expected",
        [(100, "good"), (80, "good"), (79.9, "fair"), (60, "fair"),
         (59.9, "poor"), (40, "poor"), (39.9, "bad"), (0, "bad")],
    )
    def test_band_boundaries(self, score, expected):
        assert score_band(score) == expected


class TestChecklistScoring:
    def test_all_yes_is_a_perfect_score(self):
        score, breakdown = score_checklist({code: True for code in item_codes()})
        assert score == 100.0
        assert breakdown["satisfied"] == TOTAL_ITEMS
        assert breakdown["skipped"] is False

    def test_all_no_is_zero(self):
        score, _ = score_checklist({code: False for code in item_codes()})
        assert score == 0.0

    def test_empty_answers_returns_none_not_zero(self):
        """None means "skipped", which is different from "answered badly"."""
        score, breakdown = score_checklist({})
        assert score is None
        assert breakdown["skipped"] is True
        score, breakdown = score_checklist(None)
        assert score is None

    def test_unanswered_items_count_as_not_satisfied(self):
        """Answering nothing must not score full marks."""
        codes = item_codes()
        score, breakdown = score_checklist({codes[0]: True})
        assert breakdown["answered"] == 1
        # Scores are rounded to 2dp, so compare with an absolute tolerance
        # rather than against the exact repeating fraction.
        assert score == pytest.approx(100.0 / TOTAL_ITEMS, abs=0.01)
        assert breakdown["satisfied"] == 1

    def test_partial_answers(self):
        codes = item_codes()
        score, breakdown = score_checklist(
            {codes[0]: True, codes[1]: True, codes[2]: False}
        )
        assert breakdown["answered"] == 3
        assert score == pytest.approx(200.0 / TOTAL_ITEMS, abs=0.01)

    def test_unknown_codes_are_reported_and_ignored(self):
        score, breakdown = score_checklist(
            {code: True for code in item_codes()} | {"not_a_real_item": True}
        )
        assert breakdown["ignored_codes"] == ["not_a_real_item"]
        assert score == 100.0

    def test_describe_checklist_marks_answers(self):
        codes = item_codes()
        rows = describe_checklist({codes[0]: True})
        by_code = {row["code"]: row for row in rows}
        assert by_code[codes[0]]["answered"] is True
        assert by_code[codes[0]]["satisfied"] is True
        assert by_code[codes[1]]["answered"] is False
        assert by_code[codes[1]]["answer"] is None
        assert by_code[codes[1]]["satisfied"] is False

    def test_describe_checklist_empty_when_skipped(self):
        assert describe_checklist(None) == []
        assert describe_checklist({}) == []

    def test_there_are_six_checklist_items(self):
        assert TOTAL_ITEMS == 6
