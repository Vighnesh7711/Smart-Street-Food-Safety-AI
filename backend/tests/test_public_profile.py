"""Public stall profile endpoint.

The most important test in this file is `test_response_keys_are_exactly_the_allow_list`.
Everything else checks behaviour; that one checks the boundary.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.constants import DISCLAIMER
from app.db.session import get_db
from app.main import app
from app.models.enums import CheckStatus, ScanStatus, UserRole
from app.models.hygiene_check import HygieneCheck
from app.models.hygiene_score import HygieneScore
from app.models.product import Product
from app.models.stall import Stall
from app.models.user import User
from app.models.vendor import Vendor
from app.services.qr import service as qr_service

#: The complete set of keys the public endpoint may return.
#:
#: Hardcoded on purpose. If a field is added to the response -- including
#: accidentally, by adding a column to a model that this schema is built
#: from -- this test fails and forces the addition to be deliberate.
ALLOWED_KEYS = {
    "stall_name",
    "food_category",
    "hygiene",
    "last_scan",
    "advisory_only",
    "disclaimer",
}

ALLOWED_HYGIENE_KEYS = {"score", "band", "assessed_at"}
ALLOWED_SCAN_KEYS = {"status", "scanned_at"}


@pytest.fixture
def public_setup(sqlite_session):
    """A stall with an active code, plus the owning vendor/user."""
    db = sqlite_session

    user = User(
        email="vendor@example.test",
        hashed_password="x",
        role=UserRole.VENDOR,
        full_name="Ramesh Kumar",
    )
    db.add(user)
    db.flush()
    vendor = Vendor(
        user_id=user.id, phone_number="+919876543210", preferred_language="en"
    )
    db.add(vendor)
    db.flush()
    stall = Stall(
        vendor_id=vendor.id,
        name="Ramesh Vada Pav",
        food_category="Street Food",
        address="Near Station Road, Pune",
        latitude=18.5204,
        longitude=73.8567,
    )
    db.add(stall)
    db.commit()
    db.refresh(stall)

    qr = qr_service.issue_for_stall(db, stall)
    db.commit()

    return db, stall, user, qr.code


@pytest.fixture
def public_client(public_setup):
    db, _, _, _ = public_setup
    app.dependency_overrides[get_db] = lambda: (yield db)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


class TestAllowList:
    def test_response_keys_are_exactly_the_allow_list(self, public_client, public_setup):
        """The privacy boundary, enforced.

        This endpoint is unauthenticated. Anything added to the response is
        published to the world, so the key set is asserted exactly rather
        than "contains at least".
        """
        _, _, _, code = public_setup
        body = public_client.get(f"/api/v1/public/stalls/{code}").json()
        assert set(body.keys()) == ALLOWED_KEYS

    def test_no_internal_identifiers_leak(self, public_client, public_setup):
        _, stall, _, code = public_setup
        raw = public_client.get(f"/api/v1/public/stalls/{code}").text

        # Checked against the raw body, not the parsed dict: a nested object
        # is just as public as a top-level one.
        for leaked in ("stall_id", "vendor_id", "user_id", "id"):
            assert f'"{leaked}"' not in raw, f"{leaked} must not be published"
        assert str(stall.id) not in raw.replace(code, "")

    def test_no_contact_details_leak(self, public_client, public_setup):
        """Names and phone numbers must not appear anywhere in the payload."""
        _, _, user, code = public_setup
        raw = public_client.get(f"/api/v1/public/stalls/{code}").text

        assert user.email not in raw
        assert "Ramesh Kumar" not in raw  # the vendor's full_name
        assert "+919876543210" not in raw

    def test_no_location_leak(self, public_client, public_setup):
        _, stall, _, code = public_setup
        raw = public_client.get(f"/api/v1/public/stalls/{code}").text

        assert "Station Road" not in raw
        assert "18.5204" not in raw
        assert "73.8567" not in raw

    def test_no_product_name_leak(self, public_client, public_setup):
        """A public verdict on a named brand is not a claim this system is
        in a position to make."""
        db, stall, _, code = public_setup
        db.add(
            Product(
                stall_id=stall.id,
                name="Ramesh Masala Mix",
                status=ScanStatus.SUITABLE.value,
            )
        )
        db.commit()

        raw = public_client.get(f"/api/v1/public/stalls/{code}").text
        assert "Ramesh Masala Mix" not in raw


class TestEmptyState:
    def test_unauthenticated_access_is_allowed(self, public_client, public_setup):
        _, _, _, code = public_setup
        # No Authorization header at all.
        assert public_client.get(f"/api/v1/public/stalls/{code}").status_code == 200

    def test_new_stall_has_no_assessment_or_scan(self, public_client, public_setup):
        """A never-assessed stall is a normal state, not an error."""
        _, stall, _, code = public_setup
        body = public_client.get(f"/api/v1/public/stalls/{code}").json()

        assert body["stall_name"] == stall.name
        assert body["food_category"] == "Street Food"
        assert body["hygiene"] is None
        assert body["last_scan"] is None

    def test_disclaimer_is_always_present(self, public_client, public_setup):
        _, _, _, code = public_setup
        body = public_client.get(f"/api/v1/public/stalls/{code}").json()
        assert body["advisory_only"] is True
        assert body["disclaimer"] == DISCLAIMER

    def test_cache_header_is_set(self, public_client, public_setup):
        _, _, _, code = public_setup
        response = public_client.get(f"/api/v1/public/stalls/{code}")
        assert "max-age=60" in response.headers.get("cache-control", "")


class TestPopulated:
    def test_latest_hygiene_score_is_reported(self, public_client, public_setup):
        db, stall, user, code = public_setup

        check = HygieneCheck(
            stall_id=stall.id,
            submitted_by_user_id=user.id,
            status=CheckStatus.SCORED.value,
            coverage_ok=True,
        )
        db.add(check)
        db.flush()
        db.add(
            HygieneScore(
                hygiene_check_id=check.id,
                visual_score=55.0,
                checklist_score=83.3,
                final_score=63.5,
                breakdown={},
                weights={"visual": 0.7, "checklist": 0.3},
                formula_version="v1",
            )
        )
        db.commit()

        body = public_client.get(f"/api/v1/public/stalls/{code}").json()
        assert set(body["hygiene"].keys()) == ALLOWED_HYGIENE_KEYS
        assert body["hygiene"]["score"] == 63.5
        # 63.5 lands in the "fair" band; the same bands the vendor app uses.
        assert body["hygiene"]["band"] == "fair"
        assert body["hygiene"]["assessed_at"] is not None

    def test_latest_score_wins_when_there_are_several(self, public_client, public_setup):
        db, stall, user, code = public_setup

        for final in (30.0, 85.0):
            check = HygieneCheck(
                stall_id=stall.id,
                submitted_by_user_id=user.id,
                status=CheckStatus.SCORED.value,
                coverage_ok=True,
            )
            db.add(check)
            db.flush()
            db.add(
                HygieneScore(
                    hygiene_check_id=check.id,
                    visual_score=final,
                    final_score=final,
                    breakdown={},
                    weights={},
                    formula_version="v1",
                )
            )
            db.commit()

        body = public_client.get(f"/api/v1/public/stalls/{code}").json()
        assert body["hygiene"]["score"] == 85.0
        assert body["hygiene"]["band"] == "good"

    def test_latest_scan_status_is_reported_without_the_product_name(
        self, public_client, public_setup
    ):
        db, stall, _, code = public_setup
        db.add(
            Product(
                stall_id=stall.id,
                name="Some Product",
                status=ScanStatus.SUITABLE.value,
            )
        )
        db.commit()

        body = public_client.get(f"/api/v1/public/stalls/{code}").json()
        assert set(body["last_scan"].keys()) == ALLOWED_SCAN_KEYS
        assert body["last_scan"]["status"] == "Suitable"
        assert body["last_scan"]["scanned_at"] is not None

    def test_unknown_status_is_omitted_rather_than_leaked(
        self, public_client, public_setup
    ):
        """A status written by a future version must not be published as a
        raw string the page cannot render or colour."""
        db, stall, _, code = public_setup
        db.add(
            Product(stall_id=stall.id, name="X", status="SomeFutureStatus")
        )
        db.commit()

        body = public_client.get(f"/api/v1/public/stalls/{code}").json()
        assert body["last_scan"] is None


class TestLookupBehaviour:
    def test_is_case_insensitive(self, public_client, public_setup):
        _, _, _, code = public_setup
        assert (
            public_client.get(f"/api/v1/public/stalls/{code.lower()}").status_code
            == 200
        )

    def test_unknown_code_is_404(self, public_client):
        assert public_client.get("/api/v1/public/stalls/ZZZZZZZZZZ").status_code == 404

    def test_revoked_code_is_404(self, public_client, public_setup):
        db, stall, _, code = public_setup
        qr_service.revoke(db, stall.active_qr_code)
        db.commit()

        assert public_client.get(f"/api/v1/public/stalls/{code}").status_code == 404

    def test_unknown_and_revoked_produce_identical_bodies(
        self, public_client, public_setup
    ):
        """Otherwise the endpoint reveals whether a stall ever existed."""
        db, stall, _, code = public_setup

        unknown = public_client.get("/api/v1/public/stalls/ZZZZZZZZZZ")
        qr_service.revoke(db, stall.active_qr_code)
        db.commit()
        revoked = public_client.get(f"/api/v1/public/stalls/{code}")

        assert unknown.status_code == revoked.status_code == 404
        assert unknown.json() == revoked.json()

    def test_each_of_two_stalls_resolves_to_its_own_profile(
        self, public_client, public_setup
    ):
        """Sanity: the code actually selects the stall, rather than any
        stall being returned for any valid code."""
        db, stall, _, code = public_setup
        vendor = db.query(Vendor).first()
        other = Stall(vendor_id=vendor.id, name="Other Stall", food_category="Snacks")
        db.add(other)
        db.commit()
        other_code = qr_service.issue_for_stall(db, other).code
        db.commit()

        assert (
            public_client.get(f"/api/v1/public/stalls/{code}").json()["stall_name"]
            == "Ramesh Vada Pav"
        )
        assert (
            public_client.get(f"/api/v1/public/stalls/{other_code}").json()[
                "stall_name"
            ]
            == "Other Stall"
        )
