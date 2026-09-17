"""Detections -> scored findings, especially the per-view penalty logic."""

import pytest

from app.integrations.cv_client import Detection
from app.models.enums import DetectionSource, IndicatorCode, RiskLevel, ViewCategory
from app.services.hygiene.indicators import (
    SEVERITY_MULTIPLIER,
    build_findings,
    severity_multiplier,
    summarise_for_storage,
)


class FakeIndicator:
    """Stand-in for a HygieneIndicator row."""

    def __init__(
        self,
        code: str,
        severity: str = RiskLevel.HIGH.value,
        view_penalties=None,
        is_active: bool = True,
        display_name: str | None = None,
    ):
        self.code = code
        self.default_severity = severity
        self.view_penalties = (
            view_penalties
            if view_penalties is not None
            else {
                ViewCategory.PREP_AREA.value: 18,
                ViewCategory.OVERALL.value: 8,
                ViewCategory.WASTE_AREA.value: 0,
            }
        )
        self.is_active = is_active
        self.display_name = display_name or code.replace("_", " ").title()


@pytest.fixture
def catalog():
    return [
        FakeIndicator(IndicatorCode.VISIBLE_WASTE.value),
        FakeIndicator(
            IndicatorCode.UNCOVERED_FOOD.value,
            view_penalties={ViewCategory.PREP_AREA.value: 20},
        ),
        FakeIndicator(
            IndicatorCode.CLUTTERED_SURFACE.value,
            severity=RiskLevel.MODERATE.value,
            view_penalties={ViewCategory.PREP_AREA.value: 10},
        ),
    ]


def detection(code: str, confidence: float = 1.0, raw: str = "raw") -> Detection:
    return Detection(
        label=code,
        raw_label=raw,
        confidence=confidence,
        source=DetectionSource.HEURISTIC.value,
    )


class TestViewPenalties:
    def test_waste_in_the_waste_area_carries_no_penalty(self, catalog):
        """The single most important scoring rule.

        A working bin contains waste. Penalising that would punish a vendor
        for owning one and make the whole score untrustworthy.
        """
        findings = build_findings(
            {
                ViewCategory.WASTE_AREA.value: [
                    detection(IndicatorCode.VISIBLE_WASTE.value)
                ]
            },
            catalog,
        )
        assert len(findings) == 1
        assert findings[0].penalty == 0.0
        assert findings[0].view == ViewCategory.WASTE_AREA.value

    def test_same_waste_in_the_prep_area_is_penalised_heavily(self, catalog):
        findings = build_findings(
            {
                ViewCategory.PREP_AREA.value: [
                    detection(IndicatorCode.VISIBLE_WASTE.value)
                ]
            },
            catalog,
        )
        # 18 base x 1.0 (high severity) x 1.0 confidence
        assert findings[0].penalty == pytest.approx(18.0)

    def test_view_absent_from_the_map_means_not_applicable(self, catalog):
        """uncovered_food is only mapped for prep_area, so a detection in the
        overall view produces no finding at all -- distinct from a 0 penalty."""
        findings = build_findings(
            {
                ViewCategory.OVERALL.value: [
                    detection(IndicatorCode.UNCOVERED_FOOD.value)
                ]
            },
            catalog,
        )
        assert findings == []

    def test_penalty_scales_with_confidence(self, catalog):
        low = build_findings(
            {ViewCategory.PREP_AREA.value: [detection(IndicatorCode.VISIBLE_WASTE.value, 0.5)]},
            catalog,
        )
        high = build_findings(
            {ViewCategory.PREP_AREA.value: [detection(IndicatorCode.VISIBLE_WASTE.value, 1.0)]},
            catalog,
        )
        assert low[0].penalty == pytest.approx(high[0].penalty / 2)

    def test_severity_multiplier_applies(self, catalog):
        high = build_findings(
            {ViewCategory.PREP_AREA.value: [detection(IndicatorCode.VISIBLE_WASTE.value)]},
            catalog,
        )
        moderate = build_findings(
            {ViewCategory.PREP_AREA.value: [detection(IndicatorCode.CLUTTERED_SURFACE.value)]},
            catalog,
        )
        # 18 * 1.0 vs 10 * 0.8
        assert high[0].penalty == pytest.approx(18.0)
        assert moderate[0].penalty == pytest.approx(8.0)


class TestMergingDetections:
    def test_repeated_detections_score_once(self, catalog):
        """A busy photo producing fifty cups must not multiply the penalty.

        Otherwise the score would measure how cluttered the *photo* is rather
        than how dirty the *stall* is, and any dense image would zero out.
        """
        findings = build_findings(
            {
                ViewCategory.PREP_AREA.value: [
                    detection(IndicatorCode.VISIBLE_WASTE.value, 0.4)
                    for _ in range(50)
                ]
            },
            catalog,
        )
        assert len(findings) == 1
        assert findings[0].detection_count == 50
        # Confident about the worst one, not 50x the penalty.
        assert findings[0].penalty == pytest.approx(18.0 * 0.4)

    def test_merge_keeps_the_highest_confidence(self, catalog):
        findings = build_findings(
            {
                ViewCategory.PREP_AREA.value: [
                    detection(IndicatorCode.VISIBLE_WASTE.value, 0.2),
                    detection(IndicatorCode.VISIBLE_WASTE.value, 0.9),
                    detection(IndicatorCode.VISIBLE_WASTE.value, 0.5),
                ]
            },
            catalog,
        )
        assert findings[0].confidence == pytest.approx(0.9)

    def test_same_indicator_in_two_views_produces_two_findings(self, catalog):
        findings = build_findings(
            {
                ViewCategory.PREP_AREA.value: [detection(IndicatorCode.VISIBLE_WASTE.value)],
                ViewCategory.OVERALL.value: [detection(IndicatorCode.VISIBLE_WASTE.value)],
            },
            catalog,
        )
        assert len(findings) == 2
        assert {f.view for f in findings} == {
            ViewCategory.PREP_AREA.value,
            ViewCategory.OVERALL.value,
        }

    def test_raw_labels_are_retained_for_traceability(self, catalog):
        findings = build_findings(
            {
                ViewCategory.PREP_AREA.value: [
                    detection(IndicatorCode.VISIBLE_WASTE.value, raw="cup"),
                    detection(IndicatorCode.VISIBLE_WASTE.value, raw="bottle"),
                ]
            },
            catalog,
        )
        assert set(findings[0].raw_labels) == {"cup", "bottle"}


class TestCatalogHandling:
    def test_unknown_indicator_is_skipped(self, catalog):
        """A provider emitting a label the catalog does not know must not
        silently invent a finding -- a model swap should not change scores
        via unmapped labels."""
        findings = build_findings(
            {ViewCategory.PREP_AREA.value: [detection("not_a_real_indicator")]},
            catalog,
        )
        assert findings == []

    def test_inactive_indicator_is_skipped(self):
        catalog = [FakeIndicator(IndicatorCode.VISIBLE_WASTE.value, is_active=False)]
        findings = build_findings(
            {ViewCategory.PREP_AREA.value: [detection(IndicatorCode.VISIBLE_WASTE.value)]},
            catalog,
        )
        assert findings == []

    def test_empty_input(self, catalog):
        assert build_findings({}, catalog) == []
        assert build_findings({ViewCategory.OVERALL.value: []}, catalog) == []


class TestOrderingAndSummary:
    def test_findings_sorted_by_penalty_descending(self, catalog):
        findings = build_findings(
            {
                ViewCategory.PREP_AREA.value: [
                    detection(IndicatorCode.CLUTTERED_SURFACE.value),
                    detection(IndicatorCode.VISIBLE_WASTE.value),
                ],
            },
            catalog,
        )
        penalties = [f.penalty for f in findings]
        assert penalties == sorted(penalties, reverse=True)

    def test_summary_is_json_serialisable_and_compact(self, catalog):
        findings = build_findings(
            {ViewCategory.PREP_AREA.value: [detection(IndicatorCode.VISIBLE_WASTE.value)]},
            catalog,
        )
        summary = summarise_for_storage(findings)
        assert isinstance(summary, list)
        assert set(summary[0]) == {"code", "view", "confidence", "penalty"}


class TestSeverityMultiplier:
    def test_documented_values(self):
        assert severity_multiplier(RiskLevel.HIGH.value) == 1.0
        assert severity_multiplier(RiskLevel.MODERATE.value) == 0.8
        assert severity_multiplier(RiskLevel.LOW.value) == 0.6

    def test_unknown_severity_falls_back_to_moderate(self):
        assert severity_multiplier("nonsense") == SEVERITY_MULTIPLIER["moderate"]

    def test_high_is_the_ceiling(self):
        """Capped at 1.0 so a configured penalty means what it says."""
        assert max(SEVERITY_MULTIPLIER.values()) == 1.0
