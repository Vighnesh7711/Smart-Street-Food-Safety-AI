"""Vendor onboarding, and the stall-scoped QR endpoints.

`onboard_vendor` had no direct test coverage through Phases 2-3 -- it was
exercised only incidentally. Phase 4 changes it (it now issues a QR code in
the same transaction), so this file covers the whole contract.
"""

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.db.session import get_db
from app.main import app
from app.models.enums import UserRole
from app.models.qr_code import QrCode
from app.models.stall import Stall
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.stall import StallCreate
from app.schemas.vendor import VendorOnboardRequest
from app.services.vendors import service as vendor_service


@pytest.fixture
def user(sqlite_session):
    db = sqlite_session
    user = User(
        email="vendor@example.test",
        hashed_password="x",
        role=UserRole.VENDOR,
        full_name="Test Vendor",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return db, user


def payload(**overrides) -> VendorOnboardRequest:
    stall = StallCreate(
        name=overrides.pop("name", "Ramesh Vada Pav"),
        food_category=overrides.pop("food_category", "Street Food"),
        address=overrides.pop("address", "Near Station Road"),
        **overrides,
    )
    return VendorOnboardRequest(
        phone_number="+919876543210",
        preferred_language="en",
        stall=stall,
        food_items=["Refined oil", "Tamarind chutney"],
    )


class TestOnboarding:
    def test_creates_vendor_and_stall(self, user):
        db, user_obj = user
        result = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload()
        )

        assert result.created is True
        assert result.vendor.user_id == user_obj.id
        assert result.stall.name == "Ramesh Vada Pav"
        assert result.stall.food_category == "Street Food"

    def test_issues_a_qr_code_in_the_same_transaction(self, user):
        """A stall without a code has no sticker and no public page, so the
        two must not be able to diverge."""
        db, user_obj = user
        result = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload()
        )

        codes = (
            db.query(QrCode).filter(QrCode.stall_id == result.stall.id).all()
        )
        assert len(codes) == 1
        assert codes[0].is_active is True
        assert len(codes[0].code) == 10
        assert result.stall.qr_code_id == codes[0].code

    def test_stall_read_still_exposes_qr_code_id(self, user):
        """The API contract is unchanged from when this was a column."""
        db, user_obj = user
        result = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload()
        )
        from app.schemas.stall import StallRead

        assert StallRead.model_validate(result.stall).qr_code_id is not None

    def test_stores_food_items(self, user):
        db, user_obj = user
        from app.models.food_item import FoodItem

        result = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload()
        )
        items = (
            db.query(FoodItem).filter(FoodItem.stall_id == result.stall.id).all()
        )
        assert {i.name for i in items} == {"Refined oil", "Tamarind chutney"}

    def test_stores_preferred_language(self, user):
        db, user_obj = user
        req = payload()
        req.preferred_language = "hi"
        result = vendor_service.onboard_vendor(db, user=user_obj, payload=req)
        assert result.vendor.preferred_language == "hi"


class TestIdempotency:
    def test_resubmitting_the_same_stall_updates(self, user):
        """A double-tap or a retry after a dropped connection must not
        produce two stalls -- or two QR codes, which the partial unique index
        would reject anyway."""
        db, user_obj = user
        first = vendor_service.onboard_vendor(db, user=user_obj, payload=payload())
        second = vendor_service.onboard_vendor(db, user=user_obj, payload=payload())

        assert second.created is False
        assert second.stall.id == first.stall.id
        assert db.query(Stall).count() == 1
        assert db.query(QrCode).count() == 1
        # The code must not be regenerated, or a printed sticker would break.
        assert second.stall.qr_code_id == first.stall.qr_code_id

    def test_resubmitting_updates_fields(self, user):
        db, user_obj = user
        vendor_service.onboard_vendor(db, user=user_obj, payload=payload())
        updated = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload(food_category="Beverages")
        )
        assert updated.stall.food_category == "Beverages"

    def test_a_different_stall_name_creates_a_second_stall(self, user):
        db, user_obj = user
        first = vendor_service.onboard_vendor(db, user=user_obj, payload=payload())
        second = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload(name="Second Stall")
        )

        assert second.stall.id != first.stall.id
        assert db.query(Stall).count() == 2
        # Each stall gets its own code.
        assert db.query(QrCode).count() == 2
        assert second.stall.qr_code_id != first.stall.qr_code_id

    def test_vendor_profile_is_not_duplicated(self, user):
        db, user_obj = user
        vendor_service.onboard_vendor(db, user=user_obj, payload=payload())
        vendor_service.onboard_vendor(db, user=user_obj, payload=payload())
        assert db.query(Vendor).count() == 1


class TestQrEndpoints:
    @pytest.fixture
    def client_and_stall(self, user):
        db, user_obj = user
        result = vendor_service.onboard_vendor(
            db, user=user_obj, payload=payload()
        )
        app.dependency_overrides[get_db] = lambda: (yield db)
        with TestClient(app) as client:
            headers = {
                "Authorization": f"Bearer {security.create_access_token(user_obj.id)}"
            }
            yield client, result.stall, headers, db
        app.dependency_overrides.clear()

    def test_qr_details(self, client_and_stall):
        client, stall, headers, _ = client_and_stall
        response = client.get(f"/api/v1/stalls/{stall.id}/qr", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["stall_id"] == stall.id
        assert body["code"] == stall.qr_code_id
        assert body["public_url"].endswith(f"/stall/{stall.qr_code_id}")
        assert body["image_url"].endswith(f"/stalls/{stall.id}/qr.png")

    def test_qr_png(self, client_and_stall):
        client, stall, headers, _ = client_and_stall
        response = client.get(f"/api/v1/stalls/{stall.id}/qr.png", headers=headers)

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_qr_png_download_disposition(self, client_and_stall):
        client, stall, headers, _ = client_and_stall
        response = client.get(
            f"/api/v1/stalls/{stall.id}/qr.png?download=1", headers=headers
        )
        assert "attachment" in response.headers.get("content-disposition", "")
        assert stall.qr_code_id in response.headers.get("content-disposition", "")

    def test_qr_png_requires_authentication(self, client_and_stall):
        """Kept authenticated on purpose: this route is keyed by the stall's
        serial id, so a public version would let anyone enumerate ids,
        harvest every QR, and recover every public code from them."""
        client, stall, _, _ = client_and_stall
        assert client.get(f"/api/v1/stalls/{stall.id}/qr.png").status_code == 401
        assert client.get(f"/api/v1/stalls/{stall.id}/qr").status_code == 401

    def test_another_vendor_cannot_fetch_the_qr(self, client_and_stall):
        client, stall, _, db = client_and_stall
        from app.models.enums import UserRole as Role

        other = User(email="other@example.test", hashed_password="x", role=Role.VENDOR)
        db.add(other)
        db.commit()
        other_headers = {
            "Authorization": f"Bearer {security.create_access_token(other.id)}"
        }

        # 404 rather than 403: the endpoint should not confirm the stall exists.
        assert (
            client.get(f"/api/v1/stalls/{stall.id}/qr", headers=other_headers).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/stalls/{stall.id}/qr.png", headers=other_headers
            ).status_code
            == 404
        )

    def test_stall_detail_still_includes_qr_code_id(self, client_and_stall):
        client, stall, headers, _ = client_and_stall
        body = client.get(f"/api/v1/stalls/{stall.id}", headers=headers).json()
        assert body["qr_code_id"] == stall.qr_code_id
