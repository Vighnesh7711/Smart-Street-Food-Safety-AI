"""QR code lifecycle: generation, resolution, revocation.

The lifecycle rules here are what keep printed stickers working, so they are
tested directly rather than only through the public endpoint.
"""

import pytest

from app.crud import qr_code as crud_qr_code
from app.models.qr_code import QrCode
from app.models.stall import Stall
from app.services.qr import service as qr_service


@pytest.fixture
def stall(sqlite_session):
    from app.models.vendor import Vendor
    from app.models.user import User
    from app.models.enums import UserRole

    db = sqlite_session
    user = User(email="v@x.test", hashed_password="x", role=UserRole.VENDOR)
    db.add(user)
    db.flush()
    vendor = Vendor(user_id=user.id)
    db.add(vendor)
    db.flush()
    stall = Stall(vendor_id=vendor.id, name="Test Stall", food_category="Snacks")
    db.add(stall)
    db.commit()
    db.refresh(stall)
    return db, stall


class TestCodeGeneration:
    def test_length(self):
        assert len(qr_service.generate_code()) == 10

    def test_excludes_look_alike_characters(self):
        """These codes get read aloud and typed from damaged stickers.

        1/I/L and 0/O are the classic confusions; U is excluded so random
        codes cannot spell unfortunate words.
        """
        codes = "".join(qr_service.generate_code() for _ in range(200))
        for forbidden in "ILOU":
            assert forbidden not in codes, f"{forbidden!r} must not appear"

    def test_only_uses_the_declared_alphabet(self):
        allowed = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        codes = "".join(qr_service.generate_code() for _ in range(100))
        assert set(codes) <= allowed

    def test_is_random(self):
        assert len({qr_service.generate_code() for _ in range(100)}) > 90


class TestNormalizeCode:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ab12cd34ef", "AB12CD34EF"),
            ("  AB12CD34EF  ", "AB12CD34EF"),
            ("Ab12Cd34Ef", "AB12CD34EF"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalization(self, raw, expected):
        assert qr_service.normalize_code(raw) == expected


class TestIssue:
    def test_issues_an_active_code(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)

        assert code.is_active is True
        assert code.stall_id == stall_obj.id
        assert len(code.code) == 10
        assert code.revoked_at is None

    def test_stall_property_reflects_the_code(self, stall):
        """`Stall.qr_code_id` is derived, so the API contract is unchanged
        from when it was a column."""
        db, stall_obj = stall
        assert stall_obj.qr_code_id is None

        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()
        db.refresh(stall_obj)
        assert stall_obj.qr_code_id == code.code

    def test_codes_are_unique_across_stalls(self, stall):
        db, stall_obj = stall
        from app.models.vendor import Vendor

        vendor = db.query(Vendor).first()
        other = Stall(vendor_id=vendor.id, name="Second Stall")
        db.add(other)
        db.commit()

        first = qr_service.issue_for_stall(db, stall_obj)
        second = qr_service.issue_for_stall(db, other)
        db.commit()
        assert first.code != second.code

    def test_a_second_active_code_is_rejected(self, stall):
        """The partial unique index is what makes "revoke then issue" safe.

        Without it, issuing a replacement before revoking the old one would
        silently produce two active codes and an ambiguous public page.
        """
        db, stall_obj = stall
        qr_service.issue_for_stall(db, stall_obj)
        db.commit()

        with pytest.raises(Exception):  # IntegrityError, dialect-specific text
            qr_service.issue_for_stall(db, stall_obj)
            db.commit()
        db.rollback()


class TestResolve:
    def test_resolves_an_active_code(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()

        resolved = qr_service.resolve_active(db, code.code)
        assert resolved is not None
        assert resolved.id == code.id

    def test_is_case_insensitive(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()

        assert qr_service.resolve_active(db, code.code.lower()) is not None

    def test_unknown_code_returns_none(self, stall):
        db, _ = stall
        assert qr_service.resolve_active(db, "ZZZZZZZZZZ") is None

    def test_empty_code_returns_none(self, stall):
        db, _ = stall
        assert qr_service.resolve_active(db, "") is None

    def test_revoked_code_does_not_resolve(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()

        qr_service.revoke(db, code)
        db.commit()

        assert qr_service.resolve_active(db, code.code) is None
        # ...but it still exists, so it can never be reissued.
        assert crud_qr_code.get_stall_by_code(db, code.code) is None
        assert qr_service.get_by_code(db, code.code) is not None


class TestRevocation:
    def test_revoke_marks_inactive_and_stamps_a_time(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()

        qr_service.revoke(db, code)
        db.commit()

        assert code.is_active is False
        assert code.revoked_at is not None

    def test_replace_revokes_then_issues(self, stall):
        db, stall_obj = stall
        original = qr_service.issue_for_stall(db, stall_obj)
        db.commit()
        original_code = original.code

        replacement = qr_service.replace_for_stall(db, stall_obj)
        db.commit()
        db.refresh(stall_obj)

        assert replacement.code != original_code
        assert replacement.is_active is True
        assert qr_service.resolve_active(db, original_code) is None
        assert stall_obj.qr_code_id == replacement.code

    def test_revoked_codes_are_never_reissued(self, stall):
        """A retired sticker must not start pointing at a different stall."""
        db, stall_obj = stall
        original = qr_service.issue_for_stall(db, stall_obj)
        db.commit()
        qr_service.revoke(db, original)
        db.commit()

        # generate_unique_code checks the whole table, not just active rows.
        for _ in range(30):
            assert qr_service.generate_unique_code(db) != original.code


class TestStallLookup:
    def test_resolves_a_stall_from_its_code(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()

        found = crud_qr_code.get_stall_by_code(db, code.code)
        assert found is not None
        assert found.id == stall_obj.id

    def test_case_insensitive(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()
        assert crud_qr_code.get_stall_by_code(db, code.code.lower()) is not None

    def test_revoked_code_yields_no_stall(self, stall):
        db, stall_obj = stall
        code = qr_service.issue_for_stall(db, stall_obj)
        db.commit()
        qr_service.revoke(db, code)
        db.commit()

        assert crud_qr_code.get_stall_by_code(db, code.code) is None

    def test_unknown_code_yields_no_stall(self, stall):
        db, _ = stall
        assert crud_qr_code.get_stall_by_code(db, "NOPE123456") is None


class TestPublicUrl:
    def test_builds_the_expected_url(self):
        assert (
            qr_service.build_public_url("AB12CD34EF", "https://food.example.com")
            == "https://food.example.com/stall/AB12CD34EF"
        )

    def test_tolerates_a_trailing_slash_on_the_base(self):
        assert (
            qr_service.build_public_url("AB12CD34EF", "https://food.example.com/")
            == "https://food.example.com/stall/AB12CD34EF"
        )

    def test_normalizes_the_code(self):
        assert (
            qr_service.build_public_url("ab12cd34ef", "https://x.test")
            == "https://x.test/stall/AB12CD34EF"
        )
