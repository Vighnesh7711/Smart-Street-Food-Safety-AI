"""phase 3: computer-vision hygiene monitoring

Revision ID: 0003_phase3_hygiene
Revises: 0002_phase2_scan
Create Date: 2026-09-17

Adds the hygiene indicator catalog, checks, submitted stall images, and
versioned scores.

Status/severity/view columns are plain VARCHAR with an application-level
enum (app/models/enums.py) rather than PostgreSQL ENUM types, matching the
Phase 2 convention: adding a new indicator or check state stays a code-only
change.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_phase3_hygiene"
down_revision = "0002_phase2_scan"
branch_labels = None
depends_on = None

# Same portable JSON/JSONB variant the models use.
_json = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Indicator catalog
    # ------------------------------------------------------------------
    op.create_table(
        "hygiene_indicators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_severity", sa.String(length=20), nullable=False),
        # view -> penalty points. A view absent from the map means the
        # indicator does not apply there; an explicit 0 means it applies but
        # carries no penalty (waste inside the waste area).
        sa.Column("view_penalties", _json, nullable=False),
        sa.Column("cv_labels", _json, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hygiene_indicators_id"), "hygiene_indicators", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_hygiene_indicators_code"),
        "hygiene_indicators",
        ["code"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 2. Checks
    # ------------------------------------------------------------------
    op.create_table(
        "hygiene_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stall_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("missing_views", _json, nullable=False),
        sa.Column(
            "coverage_ok", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("indicators_found", _json, nullable=False),
        sa.Column("checklist", _json, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["stall_id"], ["stalls.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hygiene_checks_id"), "hygiene_checks", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_hygiene_checks_stall_id"), "hygiene_checks", ["stall_id"], unique=False
    )
    op.create_index(
        op.f("ix_hygiene_checks_status"), "hygiene_checks", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_hygiene_checks_created_at"),
        "hygiene_checks",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hygiene_checks_submitted_by_user_id"),
        "hygiene_checks",
        ["submitted_by_user_id"],
        unique=False,
    )
    # GIN on the findings summary so the reviewer dashboard can filter
    # "stalls where visible_waste was detected" without scanning every row's
    # JSON blob. PostgreSQL-only; JSONB is what the models use on PG.
    op.create_index(
        "ix_hygiene_checks_indicators_found_gin",
        "hygiene_checks",
        ["indicators_found"],
        unique=False,
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # 3. Submitted images
    # ------------------------------------------------------------------
    op.create_table(
        "stall_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hygiene_check_id", sa.Integer(), nullable=False),
        sa.Column("stall_id", sa.Integer(), nullable=False),
        sa.Column("view_category", sa.String(length=30), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("quality", _json, nullable=True),
        sa.Column("detections", _json, nullable=True),
        sa.Column("phash", sa.String(length=32), nullable=True),
        sa.Column("duplicate_of_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["hygiene_check_id"], ["hygiene_checks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["stall_id"], ["stalls.id"]),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["stall_images.id"]),
        sa.PrimaryKeyConstraint("id"),
        # A retake replaces the image for that view rather than accumulating
        # rows, so the score cannot depend on submission order.
        sa.UniqueConstraint(
            "hygiene_check_id", "view_category", name="uq_stall_image_view"
        ),
    )
    op.create_index(op.f("ix_stall_images_id"), "stall_images", ["id"], unique=False)
    op.create_index(
        op.f("ix_stall_images_stall_id"), "stall_images", ["stall_id"], unique=False
    )
    op.create_index(
        op.f("ix_stall_images_phash"), "stall_images", ["phash"], unique=False
    )

    # ------------------------------------------------------------------
    # 4. Scores
    # ------------------------------------------------------------------
    op.create_table(
        "hygiene_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hygiene_check_id", sa.Integer(), nullable=False),
        sa.Column("visual_score", sa.Float(), nullable=False),
        sa.Column("checklist_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("breakdown", _json, nullable=False),
        sa.Column("weights", _json, nullable=False),
        sa.Column("formula_version", sa.String(length=16), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["hygiene_check_id"], ["hygiene_checks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hygiene_scores_id"), "hygiene_scores", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_hygiene_scores_hygiene_check_id"),
        "hygiene_scores",
        ["hygiene_check_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hygiene_scores_final_score"),
        "hygiene_scores",
        ["final_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("hygiene_scores")
    op.drop_table("stall_images")
    op.drop_index("ix_hygiene_checks_indicators_found_gin", table_name="hygiene_checks")
    op.drop_table("hygiene_checks")
    op.drop_table("hygiene_indicators")
