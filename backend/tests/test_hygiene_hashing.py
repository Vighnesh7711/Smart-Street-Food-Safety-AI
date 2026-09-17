"""Perceptual hashing and the duplicate-photo guard."""

import numpy as np
import pytest

from app.services.hygiene.duplicate import (
    dhash,
    find_duplicate,
    hamming_distance,
    is_duplicate,
)


def _image(seed: int, size: int = 256) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (size, size, 3), dtype=np.uint8)


@pytest.fixture
def gradient():
    """A structured image with variation in BOTH axes.

    dHash compares each pixel with its right-hand neighbour, so an image with
    no horizontal variation (a pure vertical ramp) hashes to all-zero
    regardless of its content -- a degenerate input that would make several
    of these tests pass vacuously.
    """
    ys, xs = np.mgrid[0:256, 0:256]
    ramp = ((ys + xs) % 256).astype(np.uint8)
    return np.stack([ramp, ramp, ramp], axis=-1)


class TestHashProperties:
    def test_identical_images_hash_identically(self, gradient):
        assert dhash(gradient) == dhash(gradient.copy())

    def test_hash_is_hex_of_expected_width(self, gradient):
        value = dhash(gradient)
        assert len(value) == 16
        int(value, 16)  # must parse as hex

    def test_empty_image_returns_empty_string(self):
        assert dhash(np.zeros((0, 0, 3), np.uint8)) == ""

    def test_different_images_hash_differently(self):
        a, b = _image(1), _image(2)
        assert hamming_distance(dhash(a), dhash(b)) > 5

    def test_hash_is_stable_across_runs(self, gradient):
        assert len({dhash(gradient) for _ in range(5)}) == 1


class TestBrightnessRobustness:
    def test_survives_a_brightness_shift(self, gradient):
        """dHash encodes gradients, not absolute brightness.

        This is the property that matters in practice: two photos of the same
        stall taken seconds apart differ in exposure, and a hash that
        couldn't see through that would be useless.
        """
        brighter = np.clip(gradient.astype(np.int16) + 25, 0, 255).astype(np.uint8)
        assert hamming_distance(dhash(gradient), dhash(brighter)) <= 5

    def test_survives_contrast_scaling(self, gradient):
        scaled = np.clip(gradient.astype(np.float32) * 1.1, 0, 255).astype(np.uint8)
        assert hamming_distance(dhash(gradient), dhash(scaled)) <= 5

    def test_still_separates_genuinely_different_scenes(self, gradient):
        other = _image(7)
        assert hamming_distance(dhash(gradient), dhash(other)) > 5


class TestHammingDistance:
    def test_identical_hashes_are_zero_apart(self):
        assert hamming_distance("0000000000000000", "0000000000000000") == 0

    def test_single_bit_difference(self):
        assert hamming_distance("0000000000000000", "0000000000000001") == 1

    def test_all_bits_differ(self):
        assert hamming_distance("0000000000000000", "ffffffffffffffff") == 64

    @pytest.mark.parametrize("bad", ["", "zzzz", "not-hex"])
    def test_malformed_input_is_not_a_duplicate(self, bad):
        """Fails safe: a false duplicate rejection blocks a vendor from
        submitting a legitimate photo, which is worse than missing a dupe."""
        assert hamming_distance(bad, "ffffffffffffffff") == 64

    def test_symmetric(self):
        a, b = "0123456789abcdef", "fedcba9876543210"
        assert hamming_distance(a, b) == hamming_distance(b, a)


class TestFindDuplicate:
    def test_finds_the_close_match(self, gradient):
        target = dhash(gradient)
        brighter = np.clip(gradient.astype(np.int16) + 15, 0, 255).astype(np.uint8)
        existing = [(1, dhash(_image(3))), (2, dhash(brighter))]

        result = find_duplicate(target, existing, threshold=5)
        assert result is not None
        assert result[0] == 2  # the near-identical one, not a random image

    def test_returns_none_when_nothing_is_close(self, gradient):
        existing = [(1, dhash(_image(11))), (2, dhash(_image(12)))]
        assert find_duplicate(dhash(gradient), existing, threshold=2) is None

    def test_returns_the_closest_of_several(self, gradient):
        """Distances are computed rather than assumed.

        A constant brightness offset does NOT change a dHash (that is the
        point of the algorithm), so "near" cannot be built by adding a
        constant -- it needs a structural change.
        """
        slightly_changed = gradient.copy()
        slightly_changed[100:150, :, :] = 0
        unrelated = _image(99)

        d_close = hamming_distance(dhash(gradient), dhash(slightly_changed))
        d_far = hamming_distance(dhash(gradient), dhash(unrelated))
        assert d_close < d_far, "fixture must produce two distinguishable distances"

        result = find_duplicate(
            dhash(gradient),
            [(1, dhash(unrelated)), (2, dhash(slightly_changed))],
            threshold=64,
        )
        assert result is not None
        assert result[0] == 2
        assert result[1] == d_close

    def test_empty_candidate_hash_returns_none(self, gradient):
        assert find_duplicate("", [(1, dhash(gradient))], threshold=5) is None

    def test_no_existing_images(self, gradient):
        assert find_duplicate(dhash(gradient), [], threshold=5) is None

    def test_is_duplicate_threshold_boundary(self):
        assert is_duplicate("0000000000000000", "0000000000000007", 3) is True
        assert is_duplicate("0000000000000000", "000000000000000f", 3) is False
