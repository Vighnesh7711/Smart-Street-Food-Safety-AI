"""QR image rendering.

The strongest test here decodes the rendered image back with OpenCV rather
than merely asserting that PNG bytes exist. A sticker that renders but does
not scan is the one failure that only shows up in the field, on a phone,
in front of a customer.
"""

import numpy as np
import pytest

from app.services.qr import service as qr_service

PAYLOAD = "https://food.example.com/stall/AB12CD34EF"


def _decode(png: bytes) -> str:
    """Decode a rendered QR back to text, the way a phone would."""
    import cv2

    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert image is not None, "rendered bytes are not a readable image"
    data, _points, _straight = cv2.QRCodeDetector().detectAndDecode(image)
    return data


class TestRoundTrip:
    def test_the_payload_survives_a_render_and_decode(self):
        """A real scanner can read what we produce."""
        assert _decode(qr_service.render_png(PAYLOAD)) == PAYLOAD

    def test_round_trips_a_realistic_stall_url(self):
        payload = qr_service.build_public_url("AB12CD34EF", "http://localhost:3000")
        assert _decode(qr_service.render_png(payload)) == payload

    @pytest.mark.parametrize("box_size", [8, 12, 20, 30])
    def test_round_trips_at_every_supported_size(self, box_size):
        assert _decode(qr_service.render_png(PAYLOAD, box_size=box_size)) == PAYLOAD


class TestDurability:
    def test_survives_damage_to_the_data_area(self):
        """Backs the error-correction choice in the code.

        Stickers live outdoors: they get scratched, rained on, and grimy.
        Error correction M recovers roughly 15% of *data* modules, so a scuff
        on the body of the code must not stop it scanning.
        """
        import cv2

        png = qr_service.render_png(PAYLOAD, box_size=20)
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        height, width = image.shape

        # A patch in the middle of the code, clear of the three finder
        # patterns in the corners -- see the test below for why that matters.
        damaged = image.copy()
        patch = int(min(height, width) * 0.12)
        top = (height - patch) // 2
        left = (width - patch) // 2
        damaged[top : top + patch, left : left + patch] = 255

        data, _points, _straight = cv2.QRCodeDetector().detectAndDecode(damaged)
        assert data == PAYLOAD

    def test_losing_a_finder_pattern_is_fatal(self):
        """Documents a real limit rather than pretending it does not exist.

        A QR code is located by three position-detection squares in the
        corners. Error correction protects data modules, NOT those markers,
        so damage covering one makes the code undetectable by any scanner --
        at any error-correction level.

        This is why the vendor screen renders the code on a plain white card
        with nothing overlapping it, and why the printed sticker should be
        placed flat rather than wrapped around a corner.
        """
        import cv2

        png = qr_service.render_png(PAYLOAD, box_size=20)
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        height, width = image.shape

        damaged = image.copy()
        patch = int(min(height, width) * 0.15)
        damaged[0:patch, 0:patch] = 255  # the top-left finder pattern

        data, _points, _straight = cv2.QRCodeDetector().detectAndDecode(damaged)
        assert data == ""

    def test_survives_a_light_even_scan(self):
        """A photo of a sticker is never a perfect render: exposure and
        contrast shift. Decoding must tolerate that."""
        import cv2

        png = qr_service.render_png(PAYLOAD, box_size=20)
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        faded = np.clip(image.astype(np.int16) * 0.75 + 45, 0, 255).astype(np.uint8)

        data, _points, _straight = cv2.QRCodeDetector().detectAndDecode(faded)
        assert data == PAYLOAD


class TestImageProperties:
    def test_is_a_png(self):
        assert qr_service.render_png(PAYLOAD)[:8] == b"\x89PNG\r\n\x1a\n"

    def test_default_size_is_print_quality(self):
        import cv2

        png = qr_service.render_png(PAYLOAD)
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        # ~740px at the default box size: printable at 300dpi and large
        # enough for a phone to lock onto from a normal distance.
        assert image.shape[0] == qr_service.png_dimensions()
        assert image.shape[0] >= 600

    def test_is_square(self):
        import cv2

        png = qr_service.render_png(PAYLOAD)
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        assert image.shape[0] == image.shape[1]

    def test_has_a_quiet_zone(self):
        """Without the 4-module border many scanners fail outright."""
        import cv2

        image = cv2.imdecode(
            np.frombuffer(qr_service.render_png(PAYLOAD), np.uint8),
            cv2.IMREAD_GRAYSCALE,
        )
        box = qr_service.clamp_box_size(None)
        # The outermost ring of modules must be white.
        assert (image[: box // 2, :] > 200).all()
        assert (image[:, : box // 2] > 200).all()

    def test_larger_code_is_a_larger_image(self):
        small = qr_service.render_png(PAYLOAD, box_size=10)
        large = qr_service.render_png(PAYLOAD, box_size=30)
        assert len(large) > len(small)


class TestBoxSizeClamping:
    """Unbounded, `?size=100000` would have the server build a multi-gigabyte
    bitmap -- a trivial denial of service on a public-facing route."""

    def test_default(self):
        assert qr_service.clamp_box_size(None) == 20

    def test_zero_is_raised_to_the_minimum(self):
        assert qr_service.clamp_box_size(0) == qr_service._MIN_BOX_SIZE

    def test_negative_is_raised_to_the_minimum(self):
        assert qr_service.clamp_box_size(-100) == qr_service._MIN_BOX_SIZE

    def test_absurd_size_is_capped(self):
        assert qr_service.clamp_box_size(100_000) == qr_service._MAX_BOX_SIZE

    def test_a_sensible_size_passes_through(self):
        assert qr_service.clamp_box_size(25) == 25

    def test_clamped_render_stays_small(self):
        png = qr_service.render_png(PAYLOAD, box_size=100_000)
        assert len(png) < 200_000

    def test_png_dimensions_tracks_the_clamp(self):
        assert qr_service.png_dimensions(100_000) == qr_service.png_dimensions(
            qr_service._MAX_BOX_SIZE
        )


class TestPayloadContent:
    def test_encodes_a_full_url_not_a_bare_code(self):
        """The reason a consumer's ordinary camera app works on our sticker.

        A bare code would require the in-app scanner, making the sticker
        useless to anyone without the app.
        """
        url = qr_service.build_public_url("AB12CD34EF", "https://food.example.com")
        decoded = _decode(qr_service.render_png(url))
        assert decoded.startswith("https://")
        assert "/stall/AB12CD34EF" in decoded

    def test_different_codes_produce_different_images(self):
        first = qr_service.render_png(
            qr_service.build_public_url("AAAAAAAAAA", "https://x.test")
        )
        second = qr_service.render_png(
            qr_service.build_public_url("BBBBBBBBBB", "https://x.test")
        )
        assert first != second
