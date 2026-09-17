"""End-to-end hygiene check: guided capture through to a stored score.

Runs the real service and API layers against SQLite with the deterministic
heuristic provider, so the assertions are about behaviour rather than about
a model's output.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core import security
from app.db.session import get_db
from app.main import app
from app.models.enums import UserRole, ViewCategory
from app.models.hygiene_score import HygieneScore
from app.models.stall import Stall
from app.models.stall_image import StallImage
from app.models.user import User
from app.models.vendor import Vendor
from app.services.hygiene import hygiene_service


def _encode(image: np.ndarray) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    assert ok
    return buffer.tobytes()


def tidy_photo(seed: int = 1, size: int = 700) -> bytes:
    """Textured but clean -- passes the quality gate, triggers nothing."""
    rng = np.random.default_rng(seed)
    image = np.full((size, size + 200, 3), 185, np.int16)
    image += rng.integers(-14, 14, image.shape)
    return _encode(np.clip(image, 0, 255).astype(np.uint8))


def cluttered_photo(seed: int = 2, size: int = 700) -> bytes:
    """Busy enough to trip the clutter and waste signals."""
    rng = np.random.default_rng(seed)
    height, width = size, size + 200
    image = np.clip(
        np.full((height, width, 3), 150, np.int16)
        + rng.integers(-25, 25, (height, width, 3)),
        0,
        255,
    ).astype(np.uint8)
    import cv2

    for _ in range(400):
        x, y = int(rng.integers(0, width - 20)), int(rng.integers(0, height - 20))
        cv2.rectangle(image, (x, y), (x + 12, y + 12), (int(rng.integers(0, 255)),) * 3, -1)
    return _encode(image)


@pytest.fixture
def tenant(seeded_hygiene):
    """A user, vendor profile, and stall, all persisted."""
    db = seeded_hygiene
    user = User(
        email="vendor@example.test",
        hashed_password="x",
        role=UserRole.VENDOR,
        full_name="Test Vendor",
    )
    db.add(user)
    db.flush()
    vendor = Vendor(user_id=user.id, preferred_language="en")
    db.add(vendor)
    db.flush()
    stall = Stall(
        vendor_id=vendor.id,
        name="Test Stall",
        food_category="Snacks",
    )
    db.add(stall)
    db.commit()
    db.refresh(stall)
    db.refresh(user)
    return db, stall, user


@pytest.fixture
def api(tenant):
    db, _, _ = tenant
    app.dependency_overrides[get_db] = lambda: (yield db)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def headers(tenant):
    _, _, user = tenant
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


def upload(client, headers, check_id, view, photo) -> dict:
    response = client.post(
        f"/api/v1/hygiene/checks/{check_id}/images",
        data={"view_category": view},
        files={"file": (f"{view}.jpg", photo, "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def complete_check(client, headers, check_id, answers=None) -> dict:
    if answers is not None:
        response = client.post(
            f"/api/v1/hygiene/checks/{check_id}/checklist",
            json={"answers": answers},
            headers=headers,
        )
        assert response.status_code == 200, response.text
    response = client.post(
        f"/api/v1/hygiene/checks/{check_id}/complete", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestGuidedCaptureFlow:
    def test_config_lists_four_views_and_six_items(self, api, headers):
        response = api.get("/api/v1/hygiene/config", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert [v["value"] for v in body["required_views"]] == [
            "overall",
            "prep_area",
            "storage_area",
            "waste_area",
        ]
        assert len(body["checklist_items"]) == 6
        assert body["disclaimer"]

    def test_each_step_names_the_next_view(self, api, headers, tenant):
        _, stall, _ = tenant
        check = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()
        check_id = check["id"]

        expected_next = ["prep_area", "storage_area", "waste_area", None]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            body = upload(api, headers, check_id, view, tidy_photo(seed=index))
            assert body["coverage"]["next_view"] == expected_next[index]

    def test_progress_advances(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]

        assert upload(api, headers, check_id, "overall", tidy_photo(1))["coverage"][
            "progress"
        ] == pytest.approx(0.25)
        assert upload(api, headers, check_id, "prep_area", tidy_photo(2))["coverage"][
            "progress"
        ] == pytest.approx(0.5)

    def test_missing_view_message_is_specific(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        upload(api, headers, check_id, "overall", tidy_photo(1))
        upload(api, headers, check_id, "prep_area", tidy_photo(2))

        body = api.get(f"/api/v1/hygiene/checks/{check_id}", headers=headers).json()
        assert body["coverage"]["missing"] == ["storage_area", "waste_area"]
        assert "storage area" in body["coverage"]["message"]
        assert "waste area" in body["coverage"]["message"]

    def test_resuming_returns_the_same_unfinished_check(self, api, headers, tenant):
        _, stall, _ = tenant
        first = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()
        second = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()
        assert first["id"] == second["id"]

    def test_a_new_check_is_created_after_one_is_scored(self, api, headers, tenant):
        _, stall, _ = tenant
        first = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, first, view, tidy_photo(10 + index))
        complete_check(api, headers, first, None)

        second = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()
        assert second["id"] != first


class TestCompletionRequirements:
    def test_incomplete_coverage_cannot_be_scored(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        upload(api, headers, check_id, "overall", tidy_photo(1))

        response = api.post(
            f"/api/v1/hygiene/checks/{check_id}/complete", headers=headers
        )
        assert response.status_code == 422
        detail = response.json()["detail"]["detail"]
        assert "storage" in detail.lower()
        assert "waste" in detail.lower()

    def test_completion_requires_all_four(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area"]):
            upload(api, headers, check_id, view, tidy_photo(20 + index))

        response = api.post(
            f"/api/v1/hygiene/checks/{check_id}/complete", headers=headers
        )
        assert response.status_code == 422
        assert "waste area" in response.json()["detail"]["detail"].lower()


class TestDuplicateGuard:
    def test_same_photo_for_two_views_is_rejected(self, api, headers, tenant):
        """The abuse that vendor tagging makes cheap."""
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        photo = tidy_photo(42)

        upload(api, headers, check_id, "overall", photo)
        response = api.post(
            f"/api/v1/hygiene/checks/{check_id}/images",
            data={"view_category": "prep_area"},
            files={"file": ("prep.jpg", photo, "image/jpeg")},
            headers=headers,
        )
        assert response.status_code == 422
        assert "same photo" in response.json()["detail"]["detail"].lower()

    def test_genuinely_different_photos_pass(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        upload(api, headers, check_id, "overall", tidy_photo(1))
        upload(api, headers, check_id, "prep_area", tidy_photo(2))
        upload(api, headers, check_id, "storage_area", cluttered_photo(3))


class TestRetake:
    def test_retake_replaces_the_image_for_that_view(self, api, headers, tenant):
        """Otherwise an older, worse photo would keep contributing."""
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        first = upload(api, headers, check_id, "overall", tidy_photo(1))
        second = upload(api, headers, check_id, "overall", tidy_photo(99))

        assert len(second["images"]) == 1
        assert second["images"][0]["id"] == first["images"][0]["id"]
        assert second["images"][0]["image_url"] != first["images"][0]["image_url"]


class TestScoringOutcome:
    def test_clean_stall_scores_well(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(30 + index))

        body = complete_check(
            api, headers, check_id, {c: True for c in [
                "covered_waste_bin", "clean_water", "no_hand_contact",
                "utensils_covered", "food_off_ground", "no_stray_animals"]}
        )

        assert body["status"] == "scored"
        assert body["score"]["final_score"] == 100.0
        assert body["score"]["band"] == "good"
        assert body["indicators_found"] == []

    def test_cluttered_stall_scores_lower(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, cluttered_photo(40 + index))

        body = complete_check(api, headers, check_id, None)

        assert body["score"]["final_score"] < 100.0
        assert len(body["indicators_found"]) > 0

    def test_waste_in_the_waste_area_costs_nothing(self, api, headers, tenant):
        """The rule the whole score's credibility rests on."""
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        upload(api, headers, check_id, "overall", tidy_photo(50))
        upload(api, headers, check_id, "prep_area", tidy_photo(51))
        upload(api, headers, check_id, "storage_area", tidy_photo(52))
        upload(api, headers, check_id, "waste_area", cluttered_photo(53))

        body = complete_check(api, headers, check_id, None)

        waste_findings = [
            f for f in body["indicators_found"] if f["view"] == "waste_area"
        ]
        assert waste_findings, "the busy waste-area photo should produce findings"
        for finding in waste_findings:
            if finding["code"] == "visible_waste":
                assert finding["penalty"] == 0.0

    def test_checklist_influences_the_score_by_30_percent(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(60 + index))

        # Every item explicitly answered "No" -- that is a checklist score of
        # 0, which is different from an empty submission (which the scoring
        # layer treats as "skipped" and reports as None).
        codes = [item["code"] for item in api.get(
            "/api/v1/hygiene/config", headers=headers
        ).json()["checklist_items"]]
        body = complete_check(api, headers, check_id, {code: False for code in codes})

        # Visual is perfect, checklist scores 0 -> 0.7 * 100.
        assert body["score"]["visual_score"] == 100.0
        assert body["score"]["checklist_score"] == 0.0
        assert body["score"]["final_score"] == pytest.approx(70.0, abs=0.01)

    def test_empty_checklist_submission_is_treated_as_skipped(self, api, headers, tenant):
        """An empty answer set carries no information, so it must not be
        scored as total non-compliance."""
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(66 + index))

        body = complete_check(api, headers, check_id, {})
        assert body["score"]["checklist_score"] is None
        assert body["score"]["final_score"] == 100.0

    def test_skipping_the_checklist_uses_visual_only(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(70 + index))

        body = complete_check(api, headers, check_id, None)
        assert body["score"]["checklist_score"] is None
        assert body["score"]["final_score"] == 100.0

    def test_disclaimer_is_always_present(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(80 + index))
        body = complete_check(api, headers, check_id, None)

        assert body["advisory_only"] is True
        assert "not an official certification" in body["disclaimer"]


class TestPersistence:
    def test_score_row_and_stall_column_are_written(self, api, headers, tenant):
        db, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(90 + index))
        body = complete_check(api, headers, check_id, None)

        score = db.query(HygieneScore).filter_by(hygiene_check_id=check_id).first()
        assert score is not None
        assert score.formula_version == "v1"
        assert score.weights == {"visual": 0.7, "checklist": 0.3}

        db.refresh(stall)
        assert stall.hygiene_score == pytest.approx(body["score"]["final_score"])

    def test_images_and_detections_are_stored(self, api, headers, tenant):
        db, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, cluttered_photo(100 + index))
        complete_check(api, headers, check_id, None)

        images = db.query(StallImage).filter_by(hygiene_check_id=check_id).all()
        assert len(images) == 4
        for image in images:
            assert image.phash, "every image should carry a perceptual hash"
            assert image.detections is not None
            assert "provider" in image.detections

    def test_photos_are_written_to_disk(self, api, headers, tenant, hygiene_uploads):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        for index, view in enumerate(["overall", "prep_area", "storage_area", "waste_area"]):
            upload(api, headers, check_id, view, tidy_photo(110 + index))

        assert len(list(hygiene_uploads.glob("*.jpg"))) == 4


class TestHistory:
    def test_history_lists_scored_checks_newest_first(self, api, headers, tenant):
        _, stall, _ = tenant
        for round_index in range(2):
            check_id = api.post(
                "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
            ).json()["id"]
            for index, view in enumerate(
                ["overall", "prep_area", "storage_area", "waste_area"]
            ):
                upload(
                    api,
                    headers,
                    check_id,
                    view,
                    tidy_photo(120 + round_index * 10 + index),
                )
            complete_check(api, headers, check_id, None)

        history = api.get("/api/v1/hygiene/checks", headers=headers).json()
        assert len(history) == 2
        assert [h["final_score"] for h in history] == [100.0, 100.0]
        assert all(h["status"] == "scored" for h in history)

    def test_unfinished_checks_are_excluded_by_default(self, api, headers, tenant):
        _, stall, _ = tenant
        api.post("/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers)

        assert api.get("/api/v1/hygiene/checks", headers=headers).json() == []

        with_unfinished = api.get(
            "/api/v1/hygiene/checks?include_unfinished=true", headers=headers
        ).json()
        assert len(with_unfinished) == 1
        assert with_unfinished[0]["missing_views"]


class TestAccessControl:
    def test_vendor_cannot_see_another_stalls_check(self, api, headers, tenant):
        """404 rather than 403, so the endpoint does not confirm the id exists."""
        db, stall, _ = tenant
        other_user = User(
            email="other@example.test", hashed_password="x", role=UserRole.VENDOR
        )
        db.add(other_user)
        db.flush()
        other_vendor = Vendor(user_id=other_user.id)
        db.add(other_vendor)
        db.flush()
        other_stall = Stall(
            vendor_id=other_vendor.id, name="Other Stall"
        )
        db.add(other_stall)
        db.commit()

        other_headers = {
            "Authorization": f"Bearer {security.create_access_token(other_user.id)}"
        }
        check = api.post(
            "/api/v1/hygiene/checks",
            data={"stall_id": other_stall.id},
            headers=other_headers,
        ).json()

        response = api.get(f"/api/v1/hygiene/checks/{check['id']}", headers=headers)
        assert response.status_code == 404

    def test_vendor_cannot_use_the_indicator_catalog_endpoint(self, api, headers):
        assert api.get("/api/v1/hygiene/indicators", headers=headers).status_code == 403

    def test_reviewer_can_read_the_indicator_catalog(self, api, seeded_hygiene):
        reviewer = User(
            email="reviewer@example.test", hashed_password="x", role=UserRole.REVIEWER
        )
        seeded_hygiene.add(reviewer)
        seeded_hygiene.commit()
        headers = {
            "Authorization": f"Bearer {security.create_access_token(reviewer.id)}"
        }

        response = api.get("/api/v1/hygiene/indicators", headers=headers)
        assert response.status_code == 200
        codes = {row["code"] for row in response.json()}
        assert "visible_waste" in codes
        assert len(codes) == 7

    def test_anonymous_access_is_rejected(self, api):
        assert api.get("/api/v1/hygiene/checks").status_code == 401


class TestQualityGate:
    def test_a_blurry_photo_is_rejected_before_storage(
        self, api, headers, tenant, hygiene_uploads
    ):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]

        flat = _encode(np.full((700, 900, 3), 128, np.uint8))
        response = api.post(
            f"/api/v1/hygiene/checks/{check_id}/images",
            data={"view_category": "overall"},
            files={"file": ("flat.jpg", flat, "image/jpeg")},
            headers=headers,
        )

        assert response.status_code == 422
        # Nothing should have been written for a rejected photo.
        assert list(hygiene_uploads.glob("*.jpg")) == []

    def test_oversized_upload_is_rejected(self, api, headers, tenant):
        _, stall, _ = tenant
        check_id = api.post(
            "/api/v1/hygiene/checks", data={"stall_id": stall.id}, headers=headers
        ).json()["id"]
        huge = b"\xff" * int(settings.HYGIENE_MAX_UPLOAD_MB * 1024 * 1024 + 2048)

        response = api.post(
            f"/api/v1/hygiene/checks/{check_id}/images",
            data={"view_category": "overall"},
            files={"file": ("huge.jpg", huge, "image/jpeg")},
            headers=headers,
        )
        assert response.status_code == 413
