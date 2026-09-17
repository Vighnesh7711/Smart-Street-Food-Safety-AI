"""Shared pytest fixtures.

Environment variables are set *before* any `app.*` import, because
`app.core.config.Settings` reads them at import time and declares
DATABASE_URL / JWT_SECRET_KEY as required. Without this, importing the app
in a test session that has no backend/.env fails immediately.

Database-backed fixtures skip rather than fail when no PostgreSQL is
reachable, so the pure-logic suite (normalization, matching, status engine,
translate fallback) stays runnable on any machine.
"""

import os

# Must precede all app imports -- see module docstring.
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL")
    or "postgresql+psycopg://postgres:postgres@localhost:5432/food_safety_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-not-for-production")
os.environ.setdefault("SCAN_TRANSLATION_ENABLED", "false")

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base_class import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


def _database_is_reachable(url: str) -> bool:
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_engine():
    """Engine bound to the test database, or a skip if unreachable."""
    if not _database_is_reachable(settings.DATABASE_URL):
        pytest.skip(
            f"No PostgreSQL reachable at {settings.DATABASE_URL!r}. "
            "Set TEST_DATABASE_URL (or DATABASE_URL) to run database tests."
        )

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """A session whose work is rolled back after each test.

    Nested in an outer transaction so tests that call `db.commit()` (as the
    onboarding service does) still leave no residue behind.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """TestClient whose get_db dependency resolves to the rolled-back session."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sqlite_session():
    """In-memory SQLite session for tests that need a database but not
    PostgreSQL specifically.

    Lets the pipeline tests (matching against the real seeded knowledge
    base, status decisions, persistence) run on any machine with no
    database server. The models use a JSON/JSONB variant and no
    Postgres-only column types, so the same DDL applies to both.

    NOT a substitute for the Postgres tests: it will not catch anything
    that depends on Postgres semantics.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        # A single shared connection, so the in-memory database is not
        # discarded when the pool hands out a second connection.
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def seeded_kb(sqlite_session):
    """SQLite session with the full ingredient knowledge base loaded."""
    from app.seeds.ingredients_seed import seed

    seed(sqlite_session)
    return sqlite_session


@pytest.fixture
def seeded_hygiene(sqlite_session):
    """SQLite session with the hygiene indicator catalog loaded."""
    from app.seeds.hygiene_seed import seed

    seed(sqlite_session)
    return sqlite_session


@pytest.fixture
def hygiene_uploads(tmp_path, monkeypatch):
    """Point hygiene uploads at a temp directory for the duration of a test."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "HYGIENE_UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def heuristic_cv(monkeypatch):
    """Force the deterministic heuristic provider.

    Tests assert against the heuristic because it is reproducible; the ONNX
    provider is exercised separately at the unit level (letterbox, NMS,
    missing-model) without needing a downloaded model.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "CV_PROVIDER", "heuristic")


@pytest.fixture
def reviewer_world(sqlite_session):
    """A reviewer plus a small register of stalls, for reviewer tests.

    Builds one stall per interesting state -- assessed and healthy, assessed
    and poor, flagged, never assessed -- so filter and sort tests have
    something to distinguish.
    """

    def _build():
        from datetime import datetime, timedelta, timezone

        from app.models.enums import (
            CheckStatus,
            FlagStatus,
            ScanStatus,
            UserRole,
        )
        from app.models.flag import Flag
        from app.models.hygiene_check import HygieneCheck
        from app.models.hygiene_score import HygieneScore
        from app.models.product import Product
        from app.models.stall import Stall
        from app.models.user import User
        from app.models.vendor import Vendor

        db = sqlite_session
        now = datetime.now(timezone.utc)

        reviewer = User(
            email="reviewer@example.test",
            hashed_password="x",
            role=UserRole.REVIEWER,
            full_name="Priya Officer",
        )
        db.add(reviewer)
        db.flush()

        def add_stall(
            name: str,
            *,
            owner: str,
            scores: list[float] | None = None,
            scan: str | None = None,
            flag: bool = False,
            days_ago: int = 5,
        ):
            user = User(
                email=f"{name.replace(' ', '')}@example.test",
                hashed_password="x",
                role=UserRole.VENDOR,
                full_name=owner,
            )
            db.add(user)
            db.flush()
            vendor = Vendor(user_id=user.id)
            db.add(vendor)
            db.flush()
            stall = Stall(
                vendor_id=vendor.id,
                name=name,
                food_category="Snacks",
                created_at=now - timedelta(days=60),
            )
            db.add(stall)
            db.commit()

            if scores:
                # `scores` reads oldest-first, so the last entry is the most
                # recent assessment -- which is what "latest score" must
                # return.
                for offset, score in enumerate(scores):
                    age = days_ago + (len(scores) - 1 - offset)
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
                            visual_score=score,
                            checklist_score=80.0,
                            final_score=score,
                            breakdown={},
                            weights={"visual": 0.7, "checklist": 0.3},
                            formula_version="v1",
                            computed_at=now - timedelta(days=age),
                        )
                    )
                db.commit()

            if scan:
                db.add(
                    Product(
                        stall_id=stall.id,
                        status=scan,
                        language_code="en",
                        confidence_score=0.8,
                        created_at=now - timedelta(days=days_ago),
                    )
                )
                db.commit()

            if flag:
                db.add(
                    Flag(
                        stall_id=stall.id,
                        reason="Prep area unswept",
                        status=FlagStatus.OPEN.value,
                        created_by_user_id=reviewer.id,
                    )
                )
                db.commit()

            return stall

        stalls = {
            "healthy": add_stall(
                "Ramesh Vada Pav",
                owner="Ramesh Kumar",
                scores=[88.0, 92.0],
                scan=ScanStatus.SUITABLE.value,
                days_ago=1,
            ),
            "flagged": add_stall(
                "Anita Chaat",
                owner="Anita Sharma",
                scores=[63.5],
                scan=ScanStatus.POTENTIAL_CONCERN.value,
                flag=True,
                days_ago=3,
            ),
            "poor": add_stall(
                "Biryani Corner",
                owner="Imran Sheikh",
                scores=[30.0],
                days_ago=10,
            ),
            "unassessed": add_stall(
                "New Stall",
                owner="Sunita Devi",
                days_ago=0,
            ),
        }
        return db, reviewer, stalls

    return _build


@pytest.fixture
def make_user(db_session):
    """Factory for persisted users with a given role."""
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.models.user import User

    counter = {"n": 0}

    def _make(role: UserRole = UserRole.VENDOR, password: str = "test-password-123"):
        counter["n"] += 1
        user = User(
            email=f"{role.value}{counter['n']}@example.test",
            hashed_password=get_password_hash(password),
            role=role,
            full_name=f"Test {role.value.title()}",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_headers(client, make_user):
    """Factory returning an Authorization header for a freshly created user."""
    from app.models.enums import UserRole

    def _headers(role: UserRole = UserRole.VENDOR, password: str = "test-password-123"):
        user = make_user(role=role, password=password)
        resp = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": user.email, "password": password},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, user

    return _headers
