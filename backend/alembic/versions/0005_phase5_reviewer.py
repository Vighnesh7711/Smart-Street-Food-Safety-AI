"""phase 5: reviewer flags

Revision ID: 0005_phase5_reviewer
Revises: 0004_phase4_qr
Create Date: 2026-09-17

Adds the `flags` table and drops `stalls.is_flagged`.

WHY THE COLUMN IS DROPPED, NOT KEPT IN SYNC
-------------------------------------------
`stalls.is_flagged` (0/1) was added in Phase 1 and never written by any code
path -- it was read only by the serializer, which always produced false.

Now that flags carry a reason, a reviewer, a timestamp, and a resolution, a
boolean would be a second, unmaintained answer to "is this stall flagged".
Two answers to the same question drift, and the one nothing writes always
drifts wrong. The API field is replaced by `has_open_flag`, derived from this
table, so consumers still get a boolean -- one that is actually true.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_phase5_reviewer"
down_revision = "0004_phase4_qr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stall_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["stall_id"], ["stalls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flags_id"), "flags", ["id"], unique=False)
    op.create_index(op.f("ix_flags_stall_id"), "flags", ["stall_id"], unique=False)
    op.create_index(op.f("ix_flags_status"), "flags", ["status"], unique=False)
    op.create_index(
        op.f("ix_flags_created_by_user_id"), "flags", ["created_by_user_id"], unique=False
    )
    op.create_index(op.f("ix_flags_created_at"), "flags", ["created_at"], unique=False)

    # Partial index for the dashboard's hot query -- "which stalls are
    # currently flagged". Closed rows are never examined by it, so the cost
    # does not grow with resolved history.
    op.create_index(
        "ix_flags_open",
        "flags",
        ["stall_id"],
        unique=False,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.drop_column("stalls", "is_flagged")


def downgrade() -> None:
    # Restored as the Phase 1 shape: a NOT NULL-free integer defaulting to 0.
    # Anything it used to hold is unrecoverable, but it never held anything --
    # no code path ever wrote to it.
    op.add_column(
        "stalls",
        sa.Column("is_flagged", sa.Integer(), nullable=True, server_default="0"),
    )
    op.drop_table("flags")
