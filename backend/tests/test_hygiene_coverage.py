"""Coverage validation and the missing-view message."""

from app.models.enums import REQUIRED_VIEWS, ViewCategory
from app.services.hygiene.coverage import describe_missing, evaluate_coverage


class TestRequiredViews:
    def test_there_are_four_required_views(self):
        assert len(REQUIRED_VIEWS) == 4

    def test_required_views_are_the_specced_four(self):
        assert {v.value for v in REQUIRED_VIEWS} == {
            "overall",
            "prep_area",
            "storage_area",
            "waste_area",
        }

    def test_each_view_has_a_prompt_and_hint(self):
        """The guided flow renders these directly, so an empty one would show
        a blank instruction to the vendor."""
        for view in REQUIRED_VIEWS:
            assert view.prompt and view.hint
            assert view.display_name


class TestEvaluateCoverage:
    def test_no_views_reports_all_four_missing(self):
        status = evaluate_coverage([])
        assert status.ok is False
        assert len(status.missing) == 4
        assert status.next_view == ViewCategory.OVERALL
        assert status.progress == 0.0

    def test_partial_reports_specific_missing_views(self):
        status = evaluate_coverage([ViewCategory.OVERALL, ViewCategory.PREP_AREA])
        assert status.ok is False
        assert status.missing == [ViewCategory.STORAGE_AREA, ViewCategory.WASTE_AREA]
        assert status.next_view == ViewCategory.STORAGE_AREA

    def test_message_names_the_missing_views(self):
        status = evaluate_coverage([ViewCategory.OVERALL, ViewCategory.PREP_AREA])
        assert "storage area" in status.message
        assert "waste area" in status.message

    def test_message_uses_natural_english_for_one_view(self):
        status = evaluate_coverage(
            [
                ViewCategory.OVERALL,
                ViewCategory.PREP_AREA,
                ViewCategory.STORAGE_AREA,
            ]
        )
        assert status.message == "Still needed: the waste area."
        # No "and" for a single item.
        assert " and " not in status.message

    def test_message_uses_and_for_two_views(self):
        status = evaluate_coverage([ViewCategory.OVERALL, ViewCategory.PREP_AREA])
        assert " and " in status.message

    def test_complete_coverage(self):
        status = evaluate_coverage(list(REQUIRED_VIEWS))
        assert status.ok is True
        assert status.missing == []
        assert status.next_view is None
        assert status.message == ""
        assert status.progress == 1.0

    def test_progress_tracks_fraction(self):
        assert evaluate_coverage([ViewCategory.OVERALL]).progress == 0.25
        assert evaluate_coverage(
            [ViewCategory.OVERALL, ViewCategory.PREP_AREA]
        ).progress == 0.5

    def test_accepts_raw_strings(self):
        """The view tag arrives from an HTTP form field."""
        status = evaluate_coverage(["overall", "prep_area", "storage_area", "waste_area"])
        assert status.ok is True

    def test_unknown_tags_are_ignored_not_fatal(self):
        # An unrecognised tag cannot satisfy a requirement, but it must not
        # fail the whole request either.
        status = evaluate_coverage(["overall", "kitchen_sink"])
        assert status.ok is False
        assert ViewCategory.OVERALL in status.present
        assert len(status.missing) == 3

    def test_duplicate_tags_do_not_inflate_progress(self):
        status = evaluate_coverage(
            [ViewCategory.OVERALL, ViewCategory.OVERALL, ViewCategory.OVERALL]
        )
        assert status.progress == 0.25

    def test_present_and_missing_are_disjoint_and_complete(self):
        status = evaluate_coverage([ViewCategory.WASTE_AREA])
        assert set(status.present) | set(status.missing) == set(REQUIRED_VIEWS)
        assert not (set(status.present) & set(status.missing))


class TestDescribeMissing:
    def test_three_items_use_serial_comma(self):
        text = describe_missing(list(REQUIRED_VIEWS)[:3])
        assert text.count(" and ") == 1
        assert "," in text
