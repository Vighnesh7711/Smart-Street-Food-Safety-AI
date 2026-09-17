"""Heuristic CV provider.

The most important tests here are the negative ones. This provider's
credibility rests on NOT firing on a clean stall: a hygiene score that flags
every tidy surface is worse than no score, because it teaches vendors to
ignore it.
"""

import numpy as np
import pytest

from app.integrations.cv_client import (
    H_EDGE,
    H_LINEAR,
    H_PEST,
    H_WASTE,
    H_WATER,
    HeuristicProvider,
    decode_image,
    downscale,
)
from app.models.enums import ViewCategory

HEIGHT, WIDTH = 600, 800


def encode(image: np.ndarray, quality: int = 95) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert ok
    return buffer.tobytes()


@pytest.fixture
def provider():
    return HeuristicProvider()


@pytest.fixture
def rng():
    return np.random.default_rng(11)


def textured(base: int, noise: int, rng) -> np.ndarray:
    """A floor/wall with real texture, like any actual photograph."""
    image = np.full((HEIGHT, WIDTH, 3), base, np.int16)
    image += rng.integers(-noise, noise, image.shape)
    return np.clip(image, 0, 255).astype(np.uint8)


class TestCleanImagesProduceNoDetections:
    """The negative cases. If any of these regress, the feature is dead."""

    def test_flat_uniform_surface(self, provider):
        image = np.full((HEIGHT, WIDTH, 3), 200, np.uint8)
        assert provider.detect(image, ViewCategory.OVERALL).detections == []

    def test_mildly_textured_clean_surface(self, provider, rng):
        """A clean but not perfectly uniform surface -- the common case."""
        image = textured(180, 6, rng)
        assert provider.detect(image, ViewCategory.OVERALL).detections == []

    def test_textured_floor_is_not_standing_water(self, provider, rng):
        """Regression: an earlier version flagged EVERY smooth surface as
        standing water, including a pristine table."""
        image = textured(120, 18, rng)
        result = provider.detect(image, ViewCategory.PREP_AREA)
        assert H_WATER not in {d.raw_label for d in result.detections}
        assert result.metrics["uniform_region_ratio"] < 0.10

    def test_dark_but_even_surface(self, provider):
        image = np.full((HEIGHT, WIDTH, 3), 40, np.uint8)
        assert provider.detect(image, ViewCategory.WASTE_AREA).detections == []


class TestDetectionSignals:
    def test_cluttered_surface_fires_on_a_busy_image(self, provider, rng):
        image = rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
        result = provider.detect(image, ViewCategory.PREP_AREA)
        labels = {d.label for d in result.detections}
        assert "cluttered_surface" in labels
        assert "visible_waste" in labels

    def test_standing_water_fires_on_a_bounded_glinting_region(self, provider, rng):
        image = textured(120, 18, rng)
        import cv2

        cv2.ellipse(image, (400, 300), (250, 160), 0, 0, 360, (150, 150, 150), -1)
        for _ in range(80):
            cv2.circle(
                image,
                (int(rng.integers(170, 630)), int(rng.integers(160, 440))),
                4,
                (250, 250, 250),
                -1,
            )
        result = provider.detect(image, ViewCategory.WASTE_AREA)
        assert H_WATER in {d.raw_label for d in result.detections}
        assert result.metrics["uniform_region_ratio"] >= 0.10

    def test_open_drain_fires_on_a_long_dark_line(self, provider):
        import cv2

        image = np.full((HEIGHT, WIDTH, 3), 90, np.uint8)
        cv2.line(image, (60, 300), (740, 330), (20, 20, 20), 26)
        result = provider.detect(image, ViewCategory.WASTE_AREA)
        assert H_LINEAR in {d.raw_label for d in result.detections}


class TestMetrics:
    def test_metrics_are_always_present(self, provider):
        """"Found nothing" and "did not run" must be distinguishable."""
        result = provider.detect(
            np.full((HEIGHT, WIDTH, 3), 200, np.uint8), ViewCategory.OVERALL
        )
        for key in (
            "edge_density",
            "small_blob_count",
            "uniform_region_ratio",
            "dark_ratio",
            "long_line_count",
        ):
            assert key in result.metrics

    def test_edge_density_is_a_fraction(self, provider, rng):
        result = provider.detect(
            rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8),
            ViewCategory.OVERALL,
        )
        assert 0.0 <= result.metrics["edge_density"] <= 1.0

    def test_results_are_json_serialisable(self, provider, rng):
        result = provider.detect(
            rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8),
            ViewCategory.OVERALL,
        )
        payload = result.to_dict()
        assert payload["provider"] == "heuristic"
        assert isinstance(payload["detections"], list)


class TestProviderContract:
    def test_deterministic(self, provider, rng):
        """Required: the API re-runs detection, and a flickering provider
        would make the score look unstable for no reason."""
        image = rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
        first = provider.detect(image, ViewCategory.PREP_AREA)
        second = provider.detect(image, ViewCategory.PREP_AREA)
        assert [d.to_dict() for d in first.detections] == [
            d.to_dict() for d in second.detections
        ]

    def test_confidence_is_never_certain(self, provider, rng):
        """A rule firing is not an object being recognised, so no heuristic
        detection may claim full confidence."""
        image = rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
        for detection in provider.detect(image, ViewCategory.OVERALL).detections:
            assert 0.0 < detection.confidence < 1.0

    def test_view_argument_does_not_change_detection_here(self, provider, rng):
        """The heuristic is view-agnostic; view-scoped weighting happens in
        services/hygiene/indicators.py. Pinned so the separation stays real."""
        image = rng.integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
        overall = provider.detect(image, ViewCategory.OVERALL)
        prep = provider.detect(image, ViewCategory.PREP_AREA)
        assert {d.label for d in overall.detections} == {d.label for d in prep.detections}

    def test_provider_name(self, provider):
        assert provider.name == "heuristic"


class TestImageHelpers:
    def test_decode_round_trips(self, rng):
        image = rng.integers(0, 255, (100, 120, 3), dtype=np.uint8)
        decoded = decode_image(encode(image))
        assert decoded.shape == (100, 120, 3)

    def test_decode_rejects_empty(self):
        from app.integrations.cv_client import CvError

        with pytest.raises(CvError):
            decode_image(b"")

    def test_decode_rejects_garbage(self):
        from app.integrations.cv_client import CvError

        with pytest.raises(CvError):
            decode_image(b"not an image at all")

    def test_downscale_caps_the_long_edge(self, rng):
        image = rng.integers(0, 255, (1200, 1600, 3), dtype=np.uint8)
        assert max(downscale(image, 800).shape[:2]) == 800

    def test_downscale_leaves_small_images_alone(self, rng):
        image = rng.integers(0, 255, (100, 120, 3), dtype=np.uint8)
        assert downscale(image, 800).shape == (100, 120, 3)
