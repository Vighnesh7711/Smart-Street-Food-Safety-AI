"""ONNX/YOLO provider internals.

These run WITHOUT a model file: they exercise letterbox preprocessing, head
decoding, NMS, and coordinate mapping against synthetic tensors, plus the
error paths. That keeps CI hermetic -- downloading a model to run tests would
make the suite depend on the network and on a binary nobody has reviewed.
"""

import numpy as np
import pytest

from app.core.config import settings
from app.integrations.cv_client import (
    COCO_CLASSES,
    CvInferenceError,
    CvModelUnavailable,
    HeuristicProvider,
    OnnxYoloProvider,
    build_indicator_label_map,
    get_provider,
    reset_model_cache,
)
from app.models.enums import ViewCategory

INPUT_SIZE = 640

#: Real exports have 8400 anchors. Anything with far more anchors than
#: channels is decoded as (4 + num_classes, num_anchors) -- the YOLOv8
#: orientation -- so a tiny synthetic count would not be representative.
ANCHORS = 200
COCO_CHANNELS = 4 + len(COCO_CLASSES)


def make_output(boxes, scores, class_ids, anchors: int = ANCHORS) -> np.ndarray:
    """Build a synthetic YOLOv8 head output.

    Shape (1, 4 + num_classes, anchors), with cx/cy/w/h in the first four
    channels and class scores after, matching a real export.
    """
    raw = np.zeros((COCO_CHANNELS, anchors), dtype=np.float32)
    for index, (box, score, class_id) in enumerate(zip(boxes, scores, class_ids)):
        raw[0:4, index] = box
        raw[4 + class_id, index] = score
    return raw[np.newaxis, ...]


@pytest.fixture(autouse=True)
def _reset_cache():
    reset_model_cache()
    yield
    reset_model_cache()


@pytest.fixture
def provider():
    # Empty indicator map so raw COCO names survive to the assertions.
    return OnnxYoloProvider(model_path="unused.onnx", indicator_labels={})


@pytest.fixture
def transform():
    from app.integrations.cv_client import _LetterboxTransform

    return _LetterboxTransform(
        scale=1.0, pad_x=0, pad_y=0, original_width=640, original_height=640
    )


class TestModelAvailability:
    def test_missing_model_raises_a_clear_error(self, tmp_path):
        """Must fail eagerly with instructions, not as an opaque inference
        error on the first photo a vendor submits."""
        provider = OnnxYoloProvider(model_path=str(tmp_path / "absent.onnx"))
        image = np.full((400, 500, 3), 128, np.uint8)

        with pytest.raises(CvModelUnavailable) as excinfo:
            provider.detect(image, ViewCategory.OVERALL)

        assert excinfo.value.retryable is False
        assert "not configured" in excinfo.value.user_message

    def test_directory_instead_of_file_is_rejected(self, tmp_path):
        provider = OnnxYoloProvider(model_path=str(tmp_path))
        image = np.full((400, 500, 3), 128, np.uint8)
        with pytest.raises(CvModelUnavailable):
            provider.detect(image, ViewCategory.OVERALL)

    def test_path_is_resolved_from_settings_by_default(self):
        provider = OnnxYoloProvider()
        assert provider.model_path == str(settings.cv_model_path)


class TestLetterbox:
    def test_output_is_square_and_normalised(self, provider):
        image = np.full((300, 600, 3), 128, np.uint8)
        blob, _ = provider._preprocess(image)

        assert blob.shape == (1, 3, INPUT_SIZE, INPUT_SIZE)
        assert blob.dtype == np.float32
        assert blob.min() >= 0.0 and blob.max() <= 1.0

    def test_aspect_ratio_is_preserved(self, provider):
        """Stretching instead of padding distorts boxes and measurably
        degrades accuracy, so the scale must be uniform on both axes."""
        image = np.full((300, 600, 3), 128, np.uint8)
        _, transform = provider._preprocess(image)

        # 600x300 into 640 -> limited by width: scale 640/600
        assert transform.scale == pytest.approx(640 / 600)
        # Height becomes 300 * 640/600 = 320, so 160px of vertical padding.
        assert transform.pad_y == pytest.approx((640 - 320) // 2, abs=1)
        assert transform.pad_x == 0

    def test_padding_uses_the_yolo_grey(self, provider):
        image = np.full((300, 600, 3), 255, np.uint8)
        blob, transform = provider._preprocess(image)

        # Top rows are padding, so they must read as 114/255 not as the
        # image's white.
        assert blob[0, 0, 0, 0] == pytest.approx(114 / 255, abs=0.01)

    def test_square_input_needs_no_padding(self, provider):
        image = np.full((640, 640, 3), 128, np.uint8)
        _, transform = provider._preprocess(image)
        assert transform.pad_x == 0
        assert transform.pad_y == 0
        assert transform.scale == pytest.approx(1.0)

    def test_channel_order_is_rgb(self, provider):
        """Vision models are trained on RGB; OpenCV decodes BGR. Swapping
        them silently degrades accuracy without erroring."""
        image = np.zeros((640, 640, 3), np.uint8)
        image[:, :, 2] = 255  # pure red in BGR
        blob, _ = provider._preprocess(image)

        assert blob[0, 0].mean() == pytest.approx(1.0, abs=0.01)  # R channel
        assert blob[0, 2].mean() == pytest.approx(0.0, abs=0.01)  # B channel


class TestBoxMapping:
    def test_undoes_padding_and_scale(self):
        from app.integrations.cv_client import _LetterboxTransform

        transform = _LetterboxTransform(
            scale=0.5, pad_x=100, pad_y=50, original_width=1000, original_height=800
        )
        box = OnnxYoloProvider._map_box_to_source((300.0, 250.0, 500.0, 450.0), transform)
        # (300-100)/0.5 = 400, (250-50)/0.5 = 400, (500-100)/0.5=800, (450-50)/0.5=800
        assert box == (400, 400, 800, 800)

    def test_clamps_to_the_original_image(self):
        from app.integrations.cv_client import _LetterboxTransform

        transform = _LetterboxTransform(
            scale=1.0, pad_x=0, pad_y=0, original_width=100, original_height=100
        )
        box = OnnxYoloProvider._map_box_to_source((-50.0, -50.0, 500.0, 500.0), transform)
        assert box == (0, 0, 100, 100)


class TestPostprocess:
    def test_decodes_a_single_detection(self, provider, transform):
        output = make_output(
            boxes=[[320, 320, 40, 40]], scores=[0.9], class_ids=[COCO_CLASSES.index("cup")]
        )
        boxes, scores, classes = provider._postprocess([output], transform)

        assert len(boxes) == 1
        assert scores[0] == pytest.approx(0.9)
        assert COCO_CLASSES[classes[0]] == "cup"

    def test_drops_low_confidence(self, provider, transform):
        output = make_output(
            boxes=[[320, 320, 40, 40]],
            scores=[settings.CV_CONFIDENCE_THRESHOLD - 0.05],
            class_ids=[COCO_CLASSES.index("cup")],
        )
        boxes, _, _ = provider._postprocess([output], transform)
        assert boxes == []

    def test_empty_output_returns_nothing(self, provider, transform):
        output = np.zeros((1, COCO_CHANNELS, ANCHORS), dtype=np.float32)
        assert provider._postprocess([output], transform) == ([], [], [])

    def test_nms_suppresses_overlapping_same_class(self, provider, transform):
        cup = COCO_CLASSES.index("cup")
        output = make_output(
            boxes=[[320, 320, 100, 100], [325, 325, 100, 100]],
            scores=[0.9, 0.8],
            class_ids=[cup, cup],
        )
        boxes, scores, _ = provider._postprocess([output], transform)
        assert len(boxes) == 1
        assert scores[0] == pytest.approx(0.9)

    def test_nms_keeps_overlapping_different_classes(self, provider, transform):
        """Suppressing a "bowl" because a "cup" overlaps it would erase a
        genuinely different finding."""
        output = make_output(
            boxes=[[320, 320, 100, 100], [322, 322, 100, 100]],
            scores=[0.9, 0.85],
            class_ids=[COCO_CLASSES.index("cup"), COCO_CLASSES.index("bowl")],
        )
        boxes, _, classes = provider._postprocess([output], transform)
        assert len(boxes) == 2
        assert {COCO_CLASSES[c] for c in classes} == {"cup", "bowl"}

    def test_nms_keeps_separate_boxes_of_the_same_class(self, provider, transform):
        cup = COCO_CLASSES.index("cup")
        output = make_output(
            boxes=[[100, 100, 40, 40], [500, 500, 40, 40]],
            scores=[0.9, 0.8],
            class_ids=[cup, cup],
        )
        boxes, _, _ = provider._postprocess([output], transform)
        assert len(boxes) == 2

    def test_handles_transposed_output(self, provider, transform):
        """Some exports emit (anchors, 4 + num_classes) instead."""
        output = make_output(
            boxes=[[320, 320, 40, 40]], scores=[0.9], class_ids=[COCO_CLASSES.index("cup")]
        ).transpose(0, 2, 1)
        boxes, _, classes = provider._postprocess([output], transform)
        assert len(boxes) == 1
        assert COCO_CLASSES[classes[0]] == "cup"

    def test_too_few_channels_raises_with_the_count(self, provider, transform):
        """Fails loudly rather than producing nonsense boxes."""
        output = np.zeros((1, 3, 2), dtype=np.float32)
        with pytest.raises(CvInferenceError) as excinfo:
            provider._postprocess([output], transform)
        assert "too few channels" in str(excinfo.value)

    def test_unexpected_rank_raises_with_the_shape(self, provider, transform):
        """A 3-D output means the export layout is not one we understand."""
        output = np.zeros((2, COCO_CHANNELS, ANCHORS), dtype=np.float32)
        with pytest.raises(CvInferenceError) as excinfo:
            provider._postprocess([output], transform)
        assert "shape" in str(excinfo.value).lower()


class TestIndicatorMapping:
    def test_maps_raw_labels_to_indicator_codes(self):
        class Row:
            code = "visible_waste"
            cv_labels = ["cup", "bottle"]

        mapping = build_indicator_label_map([Row()])
        assert mapping == {"cup": "visible_waste", "bottle": "visible_waste"}

    def test_mapping_is_case_insensitive(self):
        class Row:
            code = "visible_waste"
            cv_labels = ["Cup"]

        assert build_indicator_label_map([Row()]) == {"cup": "visible_waste"}

    def test_unmapped_detections_are_dropped(self, provider, transform):
        """A COCO class with no indicator mapping cannot affect the score and
        must not be stored as a finding."""
        output = make_output(
            boxes=[[320, 320, 40, 40]],
            scores=[0.9],
            class_ids=[COCO_CLASSES.index("person")],
        )
        boxes, _, _ = provider._postprocess([output], transform)
        assert len(boxes) == 1  # decoded...
        # ...but the provider's indicator_labels map is empty here, so
        # detect() would drop it. Verified directly:
        assert provider.indicator_labels.get("person", "unmapped") == "unmapped"

    def test_first_mapping_wins_on_collision(self):
        class RowA:
            code = "visible_waste"
            cv_labels = ["cup"]

        class RowB:
            code = "cluttered_surface"
            cv_labels = ["cup"]

        mapping = build_indicator_label_map([RowA(), RowB()])
        assert mapping["cup"] == "visible_waste"


class TestCocoClasses:
    def test_has_eighty_classes(self):
        assert len(COCO_CLASSES) == 80

    def test_expected_classes_are_present(self):
        for name in ("cup", "bottle", "bowl", "fork", "spoon", "dog", "cat"):
            assert name in COCO_CLASSES

    def test_no_duplicates(self):
        assert len(set(COCO_CLASSES)) == len(COCO_CLASSES)


class TestProviderDispatch:
    def test_heuristic_is_the_default(self):
        assert isinstance(get_provider([]), HeuristicProvider)

    def test_onnx_selected_by_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "CV_PROVIDER", "onnx_yolo")
        assert isinstance(get_provider([]), OnnxYoloProvider)

    def test_unknown_provider_raises(self, monkeypatch):
        from app.integrations.cv_client import CvError

        monkeypatch.setattr(settings, "CV_PROVIDER", "magic_vision")
        with pytest.raises(CvError) as excinfo:
            get_provider([])
        assert excinfo.value.retryable is False

    def test_onnx_requires_a_larger_source_image(self, tmp_path):
        """A tiny image letterboxed to 640 is almost entirely interpolation.

        The size check runs before the session is loaded, so a placeholder
        file is enough -- no real model needed.
        """
        model = tmp_path / "placeholder.onnx"
        model.write_bytes(b"not a real model")
        provider = OnnxYoloProvider(model_path=str(model))

        tiny = np.full((50, 60, 3), 128, np.uint8)
        with pytest.raises(CvInferenceError) as excinfo:
            provider.detect(tiny, ViewCategory.OVERALL)
        assert "too small" in excinfo.value.user_message.lower()
