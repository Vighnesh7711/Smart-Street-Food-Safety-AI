"""End-to-end scan pipeline.

Runs the real pipeline -- quality gate, extraction, normalization, matching
against the real seeded knowledge base, rule evaluation, explanation, and
persistence -- with only the OCR provider mocked. That boundary is mocked
because it is the single network call and the only part with no
deterministic output.

Backed by SQLite rather than PostgreSQL so it runs anywhere. See
conftest.py::sqlite_session for what that does and does not cover.
"""

import os

import numpy as np
import pytest

from app.core.config import settings
from app.integrations import ocr_client
from app.integrations.ocr_client import OcrError, OcrResult
from app.models.enums import ScanStatus, UserRole
from app.models.stall import Stall
from app.models.user import User
from app.models.vendor import Vendor
from app.services.products import scan_service


def label_image(width: int = 900, height: int = 600) -> bytes:
    """A synthetic image that passes the quality gate.

    Random noise gives a high Laplacian variance (so it is not "blurry") and
    a mid-range mean brightness. The gate only inspects image statistics, so
    a noise field is sufficient to exercise the pass path without shipping a
    binary fixture.
    """
    import cv2

    rng = np.random.default_rng(seed=1234)
    image = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    assert ok
    return buffer.tobytes()


def blurry_image() -> bytes:
    """A near-uniform image: no edges, so the blur check rejects it."""
    import cv2

    image = np.full((600, 900, 3), 128, dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


CHIPS_LABEL = """RAMESH FOODS PVT LTD
Potato Chips - Masala Flavour
Ingredients: Potato, Palm Oil, Refined Wheat Flour (Maida), Salt (1.5%),
Spices and Condiments, INS 211, Turmeric.
Nutrition Information
Energy 540 kcal
Net Weight 50 g
"""

MILD_LABEL = """Ingredients: Turmeric, Mustard Oil, Milk Solids, Iodised Salt
Nutrition Information
Energy 100 kcal
"""

NO_INGREDIENT_LABEL = """RAMESH FOODS PVT LTD
Net Weight 50 g   MRP Rs 20
Best before 6 months from packaging.
"""


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SCAN_UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_ocr(monkeypatch):
    """Replace the OCR provider; returns a setter so tests choose the text."""

    def _set(text: str, confidence: float | None = 0.95, fail: OcrError | None = None):
        def _run(image_bytes: bytes) -> OcrResult:
            if fail is not None:
                raise fail
            return OcrResult(
                text=text,
                confidence=confidence,
                word_count=len(text.split()),
                engine="mock",
            )

        monkeypatch.setattr(ocr_client, "run_ocr", _run)

    return _set


@pytest.fixture
def stall(seeded_kb):
    """A vendor, their user, and a stall, all persisted."""
    user = User(
        email="vendor@example.test",
        hashed_password="x",
        role=UserRole.VENDOR,
        full_name="Test Vendor",
    )
    seeded_kb.add(user)
    seeded_kb.flush()

    vendor = Vendor(user_id=user.id, preferred_language="en")
    seeded_kb.add(vendor)
    seeded_kb.flush()

    stall = Stall(
        vendor_id=vendor.id,
        name="Test Stall",
        food_category="Snacks",
    )
    seeded_kb.add(stall)
    seeded_kb.commit()
    seeded_kb.refresh(stall)
    seeded_kb.refresh(user)
    return seeded_kb, stall, user


def _scan(db, stall, user, image, language=None):
    return scan_service.scan_label(
        db, stall=stall, user=user, image_bytes=image, target_language=language
    )


class TestHappyPath:
    def test_concern_label_produces_potential_concern(
        self, stall, mock_ocr, upload_dir
    ):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status == ScanStatus.POTENTIAL_CONCERN.value
        names = {m.ingredient.canonical_name for m in outcome.matches}
        assert "Palm Oil" in names
        assert "Sodium Benzoate" in names  # via INS 211

    def test_explanation_is_generated_in_english(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        explanation = outcome.product.explanation
        assert explanation
        # The template's {ingredient} placeholder must have been filled.
        assert "{" not in explanation
        assert "Palm Oil" in explanation

    def test_rule_free_label_is_suitable(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr(MILD_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status == ScanStatus.SUITABLE.value
        assert outcome.product.retake_required is False

    def test_confidences_are_recorded_separately(self, stall, mock_ocr, upload_dir):
        """The three stage confidences must survive independently -- when a
        verdict is disputed, "OCR read it badly" and "we matched it badly"
        need different fixes."""
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL, confidence=0.91)
        outcome = _scan(db, stall_obj, user, label_image())

        product = outcome.product
        assert product.ocr_confidence == pytest.approx(0.91)
        assert product.match_confidence is not None
        assert product.rule_strength is not None
        assert product.confidence_score is not None
        assert outcome.confidences is not None
        assert product.confidence_score == pytest.approx(outcome.confidences.overall)

    def test_image_is_persisted(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.scan_image_path
        assert outcome.product.scan_image_path.startswith("/uploads/scans/")
        uploaded = list(upload_dir.glob("*.jpg"))
        assert len(uploaded) == 1
        assert uploaded[0].stat().st_size > 0


class TestPersistence:
    def test_matches_are_stored_with_evidence(self, stall, mock_ocr, upload_dir):
        """A disputed verdict must be traceable back to the label text."""
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.ingredient_matches
        for match in outcome.product.ingredient_matches:
            assert match.match_method
            assert match.match_confidence > 0

        benzoate = [
            m
            for m in outcome.product.ingredient_matches
            if m.matched_alias and "211" in m.matched_alias
        ]
        assert benzoate, "the INS 211 match should record which alias hit"
        assert benzoate[0].match_method == "e_number"

    def test_raw_ocr_text_and_section_are_stored(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert "RAMESH FOODS" in outcome.product.ocr_raw_text
        # The stored section must be the sliced ingredient list, not the
        # whole label.
        assert "Potato" in outcome.product.ingredients_text
        assert "540 kcal" not in outcome.product.ingredients_text

    def test_image_quality_metrics_are_stored(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        quality = outcome.product.image_quality
        assert quality is not None
        assert quality["ok"] is True
        assert "blur_variance" in quality["metrics"]

    def test_scan_is_attributed_to_the_user(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())
        assert outcome.product.scanned_by_user_id == user.id


class TestQualityGate:
    def test_blurry_image_short_circuits_to_needs_review(
        self, stall, mock_ocr, upload_dir
    ):
        db, stall_obj, user = stall

        def _explode(image_bytes):
            raise AssertionError("OCR must not run on an unusable image")

        import app.integrations.ocr_client as ocr_module

        ocr_module.run_ocr = _explode
        outcome = _scan(db, stall_obj, user, blurry_image())

        assert outcome.product.status == ScanStatus.NEEDS_REVIEW.value
        assert outcome.product.retake_required is True
        # Nothing was read, so no OCR confidence can exist.
        assert outcome.product.ocr_confidence is None

    def test_blurry_scan_is_still_persisted(self, stall, mock_ocr, upload_dir):
        """The retry pattern is itself a signal for the reviewer dashboard."""
        db, stall_obj, user = stall
        outcome = _scan(db, stall_obj, user, blurry_image())

        assert outcome.product.id is not None
        assert outcome.product.image_quality["issues"]

    def test_blurry_failure_is_translated_too(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        outcome = _scan(db, stall_obj, user, blurry_image(), language="en")
        assert outcome.product.explanation_translated


class TestStatusBranches:
    def test_missing_ingredient_section_is_insufficient_information(
        self, stall, mock_ocr, upload_dir
    ):
        db, stall_obj, user = stall
        mock_ocr(NO_INGREDIENT_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status == ScanStatus.INSUFFICIENT_INFORMATION.value
        # Retaking the same photo would not help.
        assert outcome.product.retake_required is False

    def test_category_restriction_becomes_application_mismatch(
        self, stall, mock_ocr, upload_dir
    ):
        db, stall_obj, user = stall
        # INS 250 (sodium nitrite) is permitted only in meat.
        stall_obj.food_category = "Snacks"
        db.commit()

        mock_ocr("Ingredients: Palm Oil, INS 250, Salt")
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status == ScanStatus.APPLICATION_MISMATCH.value

    def test_unknown_category_becomes_insufficient_information(
        self, stall, mock_ocr, upload_dir
    ):
        """A restricted ingredient on a stall with no category: we can
        neither clear it nor accuse, so we say so.

        The label deliberately contains no ingredient with a *definite*
        rule, since a definite concern outranks this case by design.
        """
        db, stall_obj, user = stall
        stall_obj.food_category = None
        db.commit()

        mock_ocr("Ingredients: INS 250, Salt, Turmeric, Milk Solids")
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status == ScanStatus.INSUFFICIENT_INFORMATION.value
        assert "category" in outcome.product.explanation.lower()

    def test_low_reported_confidence_asks_for_a_retake(
        self, stall, mock_ocr, upload_dir
    ):
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL, confidence=0.05)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status == ScanStatus.NEEDS_REVIEW.value
        assert outcome.product.retake_required is True

    def test_missing_confidence_falls_back_instead_of_zeroing(
        self, stall, mock_ocr, upload_dir
    ):
        """Vision often reports no confidence. Treating that as 0.0 would
        send every scan to Needs review."""
        db, stall_obj, user = stall
        mock_ocr(CHIPS_LABEL, confidence=None)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.status != ScanStatus.NEEDS_REVIEW.value
        assert outcome.product.ocr_confidence > 0.0


class TestOcrFailure:
    def test_ocr_error_raises_scan_error(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        mock_ocr("", fail=OcrError("provider down", "Try again shortly.", retryable=True))

        with pytest.raises(scan_service.ScanError) as excinfo:
            _scan(db, stall_obj, user, label_image())

        assert excinfo.value.retryable is True
        assert "Try again" in excinfo.value.user_message

    def test_no_scan_is_persisted_when_ocr_fails(self, stall, mock_ocr, upload_dir):
        """There is no assessment to record, so no misleading row is written."""
        from app.models.product import Product

        db, stall_obj, user = stall
        mock_ocr("", fail=OcrError("down", "Try later.", retryable=True))

        with pytest.raises(scan_service.ScanError):
            _scan(db, stall_obj, user, label_image())

        assert db.query(Product).count() == 0


class TestUploadValidation:
    def test_empty_upload_rejected(self, stall, upload_dir):
        db, stall_obj, user = stall
        with pytest.raises(scan_service.ScanError):
            _scan(db, stall_obj, user, b"")

    def test_oversized_upload_rejected(self, stall, upload_dir):
        db, stall_obj, user = stall
        huge = b"\xff" * int(settings.SCAN_MAX_UPLOAD_MB * 1024 * 1024 + 1024)
        with pytest.raises(scan_service.ScanError) as excinfo:
            _scan(db, stall_obj, user, huge)
        assert "larger than" in excinfo.value.user_message


class TestLanguageHandling:
    def test_vendor_preferred_language_is_used(self, stall, mock_ocr, upload_dir):
        db, stall_obj, user = stall
        vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
        vendor.preferred_language = "hi"
        db.commit()

        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        assert outcome.product.language_code == "hi"

    def test_translation_failure_falls_back_without_breaking_the_scan(
        self, stall, mock_ocr, upload_dir, monkeypatch
    ):
        """The headline requirement: a translate outage must not break a scan."""
        db, stall_obj, user = stall
        vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
        vendor.preferred_language = "hi"
        db.commit()

        monkeypatch.setattr(settings, "SCAN_TRANSLATION_ENABLED", True)
        monkeypatch.setattr(
            "app.integrations.translate_client._run_provider",
            lambda texts, target: (_ for _ in ()).throw(RuntimeError("down")),
        )

        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        # The scan still completed, with a verdict.
        assert outcome.product.status == ScanStatus.POTENTIAL_CONCERN.value
        assert outcome.product.translation_failed is True
        # English is shown instead of nothing.
        assert outcome.product.explanation_translated == outcome.product.explanation
        assert outcome.product.explanation


# ---------------------------------------------------------------------------
# The whole pipeline with the REAL local model
# ---------------------------------------------------------------------------
# Opt-in for the same reason as tests/test_indictrans2_model.py: it loads
# ~1.1 GB of weights and takes seconds. Everything else in this file mocks the
# translation seam; this one does not, which is the only test that proves the
# vendor actually gets Hindi.
#
#     RUN_TRANSLATION_MODEL_TESTS=1 pytest tests/test_scan_pipeline.py -k real_model


def _has_devanagari(text: str) -> bool:
    return any(0x0900 <= ord(char) < 0x0980 for char in text)


@pytest.mark.translation_model
@pytest.mark.skipif(
    os.environ.get("RUN_TRANSLATION_MODEL_TESTS") != "1",
    reason="opt-in: set RUN_TRANSLATION_MODEL_TESTS=1 (loads ~1.1 GB of weights)",
)
class TestRealModelEndToEnd:
    """image -> (mocked Vision OCR) -> English explanation -> IndicTrans2.

    Vision is the one boundary still mocked, because it is a live network call
    that needs a credential. Everything downstream of it is real: the quality
    gate, extraction, matching against the seeded knowledge base, rule
    evaluation, explanation, the local model, and persistence.
    """

    def test_vendor_gets_hindi_all_the_way_to_the_row(
        self, stall, mock_ocr, upload_dir, monkeypatch
    ):
        from app.integrations import translate_client

        db, stall_obj, user = stall
        vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
        vendor.preferred_language = "hi"
        db.commit()

        monkeypatch.setattr(settings, "SCAN_TRANSLATION_ENABLED", True)
        monkeypatch.setattr(translate_client, "_runtime", None)
        translate_client.clear_cache()

        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        product = outcome.product
        # The verdict is unchanged by translation -- it is computed from the
        # English explanation and must not depend on the translation step.
        assert product.status == ScanStatus.POTENTIAL_CONCERN.value
        assert product.language_code == "hi"
        assert product.translation_failed is False

        assert product.explanation, "canonical English is always stored"
        assert product.explanation_translated != product.explanation
        assert _has_devanagari(product.explanation_translated), (
            f"expected Devanagari, got {product.explanation_translated!r}"
        )

    def test_english_vendor_is_not_sent_through_the_model(
        self, stall, mock_ocr, upload_dir, monkeypatch
    ):
        """The default path must stay free: an English vendor costs no
        inference at all."""
        from app.integrations import translate_client

        db, stall_obj, user = stall
        monkeypatch.setattr(settings, "SCAN_TRANSLATION_ENABLED", True)
        monkeypatch.setattr(translate_client, "_runtime", None)
        translate_client.clear_cache()

        def _explode(*args, **kwargs):
            raise AssertionError("English must not reach the model")

        monkeypatch.setattr(translate_client, "_run_provider", _explode)

        mock_ocr(CHIPS_LABEL)
        outcome = _scan(db, stall_obj, user, label_image())

        product = outcome.product
        assert product.language_code == "en"
        assert product.translation_failed is False
        # Passthrough rather than a failure: the English text is the answer.
        assert product.explanation_translated == product.explanation


@pytest.fixture
def scan_api(stall, mock_ocr, upload_dir):
    """TestClient wired to the SQLite session, authenticated as the vendor."""
    from fastapi.testclient import TestClient

    from app.core import security
    from app.db.session import get_db
    from app.main import app

    db, stall_obj, user = stall

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    headers = {"Authorization": f"Bearer {security.create_access_token(user.id)}"}
    with TestClient(app) as client:
        yield client, stall_obj, db, headers
    app.dependency_overrides.clear()


class TestScanEndpointContract:
    """The HTTP layer, which no earlier phase covered.

    The mobile client reads `explanation_translated`, `language_code` and
    `translation_failed` straight off this body, so a rename in the response
    model would break the result card with nothing in the backend suite
    failing. This is that net.
    """

    def _post(self, client, stall_obj, headers):
        return client.post(
            f"{settings.API_V1_STR}/products/scan",
            data={"stall_id": stall_obj.id},
            files={"file": ("label.jpg", label_image(), "image/jpeg")},
            headers=headers,
        )

    def test_endpoint_still_works_and_returns_the_expected_fields(
        self, scan_api, mock_ocr
    ):
        client, stall_obj, _db, headers = scan_api
        mock_ocr(CHIPS_LABEL)

        response = self._post(client, stall_obj, headers)

        assert response.status_code == 201, response.text
        body = response.json()
        for field in (
            "status",
            "explanation",
            "explanation_translated",
            "language_code",
            "translation_failed",
        ):
            assert field in body, f"{field} missing from the scan response"

    def test_english_scan_reports_passthrough_not_failure(self, scan_api, mock_ocr):
        client, stall_obj, _db, headers = scan_api
        mock_ocr(CHIPS_LABEL)

        body = self._post(client, stall_obj, headers).json()

        assert body["language_code"] == "en"
        assert body["translation_failed"] is False
        # The frontend shows the English text as primary when nothing was
        # translated, so the two fields must agree.
        assert body["explanation_translated"] == body["explanation"]

    def test_unknown_stall_is_rejected(self, scan_api, mock_ocr):
        client, _stall_obj, _db, headers = scan_api
        mock_ocr(CHIPS_LABEL)

        response = client.post(
            f"{settings.API_V1_STR}/products/scan",
            data={"stall_id": 999999},
            files={"file": ("label.jpg", label_image(), "image/jpeg")},
            headers=headers,
        )

        assert response.status_code in (403, 404)

    def test_scan_requires_authentication(self, scan_api, mock_ocr):
        client, stall_obj, _db, _headers = scan_api
        mock_ocr(CHIPS_LABEL)

        response = client.post(
            f"{settings.API_V1_STR}/products/scan",
            data={"stall_id": stall_obj.id},
            files={"file": ("label.jpg", label_image(), "image/jpeg")},
        )

        assert response.status_code == 401

    @pytest.mark.translation_model
    @pytest.mark.skipif(
        os.environ.get("RUN_TRANSLATION_MODEL_TESTS") != "1",
        reason="opt-in: set RUN_TRANSLATION_MODEL_TESTS=1 (loads ~1.1 GB of weights)",
    )
    def test_hindi_vendor_gets_devanagari_over_http(
        self, scan_api, mock_ocr, monkeypatch
    ):
        """The whole path a real vendor takes: HTTP -> OCR (mocked) -> the
        local model -> the JSON body the phone renders."""
        from app.integrations import translate_client
        from app.models.vendor import Vendor

        client, stall_obj, db, headers = scan_api
        vendor = db.query(Vendor).filter(Vendor.id == stall_obj.vendor_id).first()
        vendor.preferred_language = "hi"
        db.commit()

        monkeypatch.setattr(settings, "SCAN_TRANSLATION_ENABLED", True)
        monkeypatch.setattr(translate_client, "_runtime", None)
        translate_client.clear_cache()
        mock_ocr(CHIPS_LABEL)

        response = self._post(client, stall_obj, headers)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["language_code"] == "hi"
        assert body["translation_failed"] is False
        assert _has_devanagari(body["explanation_translated"]), (
            f"expected Devanagari, got {body['explanation_translated']!r}"
        )
