"""phase 4: qr_codes table; stall code moves off the stalls table

Revision ID: 0004_phase4_qr
Revises: 0003_phase3_hygiene
Create Date: 2026-09-17

Phase 1 stored the public stall code as `stalls.qr_code_id` (NOT NULL
UNIQUE). Phase 4 introduces a `qr_codes` table so a stall can have its code
replaced or revoked without losing the record of what was printed.

Leaving both in place would mean two sources of truth for the value inside a
printed sticker. When they disagree, the sticker silently stops resolving --
discovered by a customer at a stall rather than by a test. So the column is
dropped and `qr_codes` becomes authoritative.

Order matters here and is not interchangeable:
    1. create qr_codes
    2. BACKFILL one active code per existing stall  <-- before the drop
    3. drop the index and column

Doing 3 before 2 would destroy every existing stall's code, irrecoverably.

The API contract is unaffected: `StallRead.qr_code_id` is still returned,
now derived from the active qr_codes row.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_phase4_qr"
down_revision = "0003_phase3_hygiene"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qr_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stall_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["stall_id"], ["stalls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_qr_codes_id"), "qr_codes", ["id"], unique=False)
    op.create_index(op.f("ix_qr_codes_code"), "qr_codes", ["code"], unique=True)
    op.create_index(op.f("ix_qr_codes_is_active"), "qr_codes", ["is_active"], unique=False)
    op.create_index(op.f("ix_qr_codes_stall_id"), "qr_codes", ["stall_id"], unique=False)

    # At most one ACTIVE code per stall. A plain UNIQUE(stall_id) would forbid
    # ever issuing a replacement; this allows history while making
    # "revoke then issue" safe under concurrency.
    op.create_index(
        "uq_qr_codes_active_stall",
        "qr_codes",
        ["stall_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    # --- Backfill BEFORE dropping anything -----------------------------
    # One active code per existing stall, inheriting the stall's created_at so
    # the code's age reflects reality rather than the migration time.
    op.execute(
        """
        INSERT INTO qr_codes (stall_id, code, is_active, created_at)
        SELECT id, qr_code_id, true, COALESCE(created_at, now())
        FROM stalls
        WHERE qr_code_id IS NOT NULL
        """
    )

    # --- Now it is safe to remove the old column -----------------------
    op.drop_index(op.f("ix_stalls_qr_code_id"), table_name="stalls")
    op.drop_column("stalls", "qr_code_id")


def downgrade() -> None:
    # Recreate the column nullable first: the table may hold rows, and adding
    # a NOT NULL column to a populated table requires either a default or a
    # backfill.
    op.add_column("stalls", sa.Column("qr_code_id", sa.String(), nullable=True))

    # Restore each stall's active code. Stalls whose only code was revoked
    # have nothing to restore and stay NULL, which the NOT NULL below would
    # reject -- so those are removed from consideration by giving them a
    # freshly generated value. Losing a revoked code is acceptable on a
    # downgrade; failing the entire migration is not.
    op.execute(
        """
        UPDATE stalls s
        SET qr_code_id = COALESCE(
            (SELECT q.code FROM qr_codes q
              WHERE q.stall_id = s.id AND q.is_active
              ORDER BY q.id LIMIT 1),
            upper(substr(md5(random()::text), 1, 10))
        )
        """
    )

    op.alter_column("stalls", "qr_code_id", nullable=False, existing_type=sa.String())
    op.create_index(
        op.f("ix_stalls_qr_code_id"), "stalls", ["qr_code_id"], unique=True
    )

    op.drop_index("uq_qr_codes_active_stall", table_name="qr_codes")
    op.drop_table("qr_codes")
