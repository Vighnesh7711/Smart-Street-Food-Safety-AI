"""Vendor detail: score history, scan history, images, delta."""

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.db.session import get_db
from app.main import app
from app.models.hygiene_check import HygieneCheck
from app.models.product import Product
from app.models.product_ingredient import ProductIngredient
from app.models.stall_image import StallImage


@pytest.fixture
def world(reviewer_world):
    db, reviewer, stalls = reviewer_world()
    app.dependency_overrides[get_db] = lambda: (yield db)
    with TestClient(app) as client:
        headers = {
            "Authorization": f"Bearer {security.create_access_token(reviewer.id)}"
        }
        yield client, db, reviewer, stalls, headers
    app.dependency_overrides.clear()


def detail(client, headers, stall_id):
    response = client.get(f"/api/v1/reviewer/vendors/{stall_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestBasics:
    def test_returns_stall_and_vendor(self, world):
        client, _, _, stalls, headers = world
        body = detail(client, headers, stalls["healthy"].id)

        assert body["stall_name"] == "Ramesh Vada Pav"
        assert body["vendor_name"] == "Ramesh Kumar"
        assert body["food_category"] == "Snacks"

    def test_unknown_stall_is_404(self, world):
        client, _, _, _, headers = world
        assert (
            client.get("/api/v1/reviewer/vendors/99999", headers=headers).status_code
            == 404
        )

    def test_unassessed_stall_returns_nulls_not_zeros(self, world):
        """A stall with no assessment has no score -- reporting 0 would read
        as the worst possible result."""
        client, _, _, stalls, headers = world
        body = detail(client, headers, stalls["unassessed"].id)

        assert body["current_score"] is None
        assert body["current_band"] is None
        assert body["score_delta"] is None
        assert body["hygiene_history"] == []


class TestScoreHistory:
    def test_history_is_oldest_first(self, world):
        """Chart order. Reversing it would draw the trend backwards."""
        client, _, _, stalls, headers = world
        body = detail(client, headers, stalls["healthy"].id)
        scores = [point["score"] for point in body["hygiene_history"]]
        assert scores == [88.0, 92.0]

    def test_current_score_is_the_latest(self, world):
        client, _, _, stalls, headers = world
        body = detail(client, headers, stalls["healthy"].id)
        assert body["current_score"] == 92.0
        assert body["current_band"] == "good"

    def test_delta_is_against_the_previous_assessment(self, world):
        client, _, _, stalls, headers = world
        body = detail(client, headers, stalls["healthy"].id)
        assert body["score_delta"] == pytest.approx(4.0)

    def test_delta_is_null_with_a_single_assessment(self, world):
        """Showing "+63" against an implicit zero would read as a huge
        improvement that never happened."""
        client, _, _, stalls, headers = world
        body = detail(client, headers, stalls["flagged"].id)
        assert len(body["hygiene_history"]) == 1
        assert body["score_delta"] is None

    def test_delta_can_be_negative(self, world):
        client, db, _, stalls, headers = world
        from datetime import datetime, timedelta, timezone

        from app.models.hygiene_score import HygieneScore

        stall_id = stalls["healthy"].id
        check = HygieneCheck(stall_id=stall_id, status="scored", coverage_ok=True)
        db.add(check)
        db.flush()
        db.add(
            HygieneScore(
                hygiene_check_id=check.id,
                visual_score=40.0,
                final_score=40.0,
                breakdown={},
                weights={},
                formula_version="v1",
                computed_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()

        body = detail(client, headers, stall_id)
        assert body["current_score"] == 40.0
        assert body["score_delta"] == pytest.approx(-52.0)

    def test_history_points_carry_their_band_and_components(self, world):
        client, _, _, stalls, headers = world
        point = detail(client, headers, stalls["healthy"].id)["hygiene_history"][0]
        assert point["band"] == "good"
        assert point["visual_score"] == 88.0
        assert point["checklist_score"] == 80.0
        assert point["formula_version"] == "v1"


class TestScanHistory:
    def test_newest_first(self, world):
        client, db, _, stalls, headers = world
        from datetime import datetime, timedelta, timezone

        stall_id = stalls["healthy"].id
        db.add(
            Product(
                stall_id=stall_id,
                status="Potential concern",
                language_code="hi",
                created_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()

        body = detail(client, headers, stall_id)
        assert body["scan_history"][0]["status"] == "Potential concern"

    def test_ingredient_counts_are_included(self, world):
        client, db, _, stalls, headers = world
        from app.models.ingredient import Ingredient

        stall_id = stalls["healthy"].id
        product = db.query(Product).filter(Product.stall_id == stall_id).first()

        # Three distinct ingredients: product_ingredients is unique on
        # (product_id, ingredient_id), so duplicates are rejected by design.
        ingredients = [
            Ingredient(
                canonical_name=name,
                category="Fat/Oil",
                default_risk_level="high",
            )
            for name in ("Palm Oil", "Sodium Benzoate", "Tartrazine")
        ]
        db.add_all(ingredients)
        db.flush()
        db.add_all(
            [
                ProductIngredient(product_id=product.id, ingredient_id=item.id)
                for item in ingredients
            ]
        )
        db.commit()

        row = next(
            item
            for item in detail(client, headers, stall_id)["scan_history"]
            if item["scan_id"] == product.id
        )
        assert row["ingredient_count"] == 3

    def test_translation_failure_is_surfaced(self, world):
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        product = db.query(Product).filter(Product.stall_id == stall_id).first()
        product.translation_failed = True
        db.commit()

        row = detail(client, headers, stall_id)["scan_history"][0]
        assert row["translation_failed"] is True

    def test_unknown_status_is_skipped(self, world):
        """A status written by a future version must not be rendered as an
        uncolourable string."""
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        db.add(Product(stall_id=stall_id, status="SomeFutureStatus"))
        db.commit()

        statuses = [row["status"] for row in detail(client, headers, stall_id)["scan_history"]]
        assert "SomeFutureStatus" not in statuses


class TestImages:
    def _add_image(self, db, stall_id, **overrides):
        check = db.query(HygieneCheck).filter(HygieneCheck.stall_id == stall_id).first()
        payload = overrides.pop(
            "detections",
            {
                "provider": "heuristic",
                "metrics": {"image_width": 900.0, "image_height": 700.0},
                "detections": [
                    {
                        "label": "visible_waste",
                        "raw_label": "heuristic:waste_density",
                        "confidence": 0.72,
                        "bbox": [100, 50, 400, 300],
                        "source": "heuristic",
                    }
                ],
            },
        )
        image = StallImage(
            hygiene_check_id=check.id,
            stall_id=stall_id,
            view_category=overrides.pop("view_category", "prep_area"),
            image_path="/uploads/hygiene/photo.jpg",
            quality=overrides.pop("quality", {"ok": True, "issues": []}),
            detections=payload,
            **overrides,
        )
        db.add(image)
        db.commit()
        return image

    def test_image_carries_its_coordinate_space(self, world):
        """Without this the overlay cannot place boxes as percentages, and a
        client would have to reimplement the detector's downscale rule."""
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        self._add_image(db, stall_id)

        image = detail(client, headers, stall_id)["images"][0]
        assert image["box_space"] == {"width": 900.0, "height": 700.0}

    def test_detections_are_returned_with_a_bbox(self, world):
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        self._add_image(db, stall_id)

        detection = detail(client, headers, stall_id)["images"][0]["detections"][0]
        assert detection["code"] == "visible_waste"
        assert detection["bbox"] == [100, 50, 400, 300]
        assert detection["confidence"] == pytest.approx(0.72)
        assert detection["raw_labels"] == ["heuristic:waste_density"]
        # Resolved server-side so the gallery needs no second request. This
        # fixture does not seed the indicator catalog, so this is the
        # fallback rendering of the code -- with the catalog seeded it would
        # be the catalog's display name.
        assert detection["display_name"] == "Visible Waste"

    def test_detections_without_a_bbox_are_omitted_from_the_overlay_list(self, world):
        """The heuristic provider emits no box for several indicators; the
        overlay is additive, so those simply do not appear in it."""
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        self._add_image(
            db,
            stall_id,
            detections={
                "provider": "heuristic",
                "metrics": {"image_width": 900.0, "image_height": 700.0},
                "detections": [
                    {
                        "label": "open_drain",
                        "raw_label": "heuristic:linear_dark_region",
                        "confidence": 0.4,
                        "bbox": None,
                        "source": "heuristic",
                    }
                ],
            },
        )

        image = detail(client, headers, stall_id)["images"][0]
        assert image["detections"] == []

    def test_image_without_recorded_dimensions_has_no_box_space(self, world):
        """Older rows written before the coordinate space was recorded must
        degrade to a list, not to a misplaced box."""
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        self._add_image(
            db,
            stall_id,
            detections={
                "provider": "heuristic",
                "metrics": {},
                "detections": [
                    {
                        "label": "visible_waste",
                        "raw_label": "x",
                        "confidence": 0.5,
                        "bbox": [1, 2, 3, 4],
                        "source": "heuristic",
                    }
                ],
            },
        )

        image = detail(client, headers, stall_id)["images"][0]
        assert image["box_space"] is None

    def test_view_display_name_is_set(self, world):
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        self._add_image(db, stall_id, view_category="waste_area")

        image = detail(client, headers, stall_id)["images"][0]
        assert image["view_category"] == "waste_area"
        assert image["view_display_name"] == "Waste Area"

    def test_quality_issues_are_surfaced(self, world):
        client, db, _, stalls, headers = world
        stall_id = stalls["healthy"].id
        self._add_image(
            db,
            stall_id,
            quality={"ok": False, "issues": ["glare", "blurry"]},
        )

        image = detail(client, headers, stall_id)["images"][0]
        assert set(image["quality_issues"]) == {"glare", "blurry"}
