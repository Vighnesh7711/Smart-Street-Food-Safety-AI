"""phase 2: ingredient knowledge base + product scan result columns

Revision ID: 0002_phase2_scan
Revises: 0001_phase1_initial
Create Date: 2026-09-17

Adds the four knowledge-base tables plus product_ingredients, and extends
`products` with the per-stage confidences and translation fields.

Note on the status/severity/category columns: these are plain VARCHAR with
an application-level enum (app/models/enums.py) rather than PostgreSQL ENUM
types. Adding a sixth scan status later is then a code-only change instead
of a migration that has to ALTER TYPE on a populated table.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_phase2_scan"
down_revision = "0001_phase1_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Knowledge base
    # ------------------------------------------------------------------
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("default_risk_level", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingredients_id"), "ingredients", ["id"], unique=False)
    op.create_index(
        op.f("ix_ingredients_canonical_name"),
        "ingredients",
        ["canonical_name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ingredients_category"), "ingredients", ["category"], unique=False
    )

    op.create_table(
        "ingredient_synonyms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column("alias_type", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_alias", name="uq_ingredient_synonym_alias"),
    )
    op.create_index(
        op.f("ix_ingredient_synonyms_id"), "ingredient_synonyms", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_ingredient_synonyms_ingredient_id"),
        "ingredient_synonyms",
        ["ingredient_id"],
        unique=False,
    )

    op.create_table(
        "ingredient_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=40), nullable=False),
        sa.Column(
            "conditions",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status_on_match", sa.String(length=40), nullable=False),
        sa.Column("explanation_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingredient_rules_id"), "ingredient_rules", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_ingredient_rules_ingredient_id"),
        "ingredient_rules",
        ["ingredient_id"],
        unique=False,
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("ingredient_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["ingredient_rules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_recommendations_id"), "recommendations", ["id"], unique=False
    )

    # ------------------------------------------------------------------
    # 2. Extend products
    # ------------------------------------------------------------------
    # Phase 1 declared these as unbounded VARCHAR; explanations and OCR text
    # are long, so widen to TEXT to avoid silent truncation.
    op.alter_column(
        "products",
        "ingredients_text",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "explanation",
        existing_type=sa.String(),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "name",
        existing_type=sa.String(),
        type_=sa.String(length=200),
        existing_nullable=True,
    )

    op.add_column("products", sa.Column("explanation_translated", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("language_code", sa.String(length=8), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "translation_failed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("products", sa.Column("scan_image_path", sa.String(length=500), nullable=True))
    op.add_column("products", sa.Column("ocr_raw_text", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("match_confidence", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("rule_strength", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "image_quality",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "retake_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("products", sa.Column("scanned_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_products_scanned_by_user_id",
        "products",
        "users",
        ["scanned_by_user_id"],
        ["id"],
    )

    op.create_index(op.f("ix_products_stall_id"), "products", ["stall_id"], unique=False)
    op.create_index(op.f("ix_products_status"), "products", ["status"], unique=False)
    op.create_index(
        op.f("ix_products_confidence_score"),
        "products",
        ["confidence_score"],
        unique=False,
    )
    op.create_index(
        op.f("ix_products_scanned_by_user_id"),
        "products",
        ["scanned_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_products_created_at"), "products", ["created_at"], unique=False
    )

    # ------------------------------------------------------------------
    # 3. Match evidence
    # ------------------------------------------------------------------
    op.create_table(
        "product_ingredients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("matched_text", sa.String(length=300), nullable=True),
        sa.Column("matched_alias", sa.String(length=200), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("match_method", sa.String(length=20), nullable=False),
        sa.Column("position_in_text", sa.Integer(), nullable=True),
        sa.Column("parsed_percent", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "ingredient_id", name="uq_product_ingredient"
        ),
    )
    op.create_index(
        op.f("ix_product_ingredients_id"), "product_ingredients", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_product_ingredients_product_id"),
        "product_ingredients",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("product_ingredients")

    op.drop_index(op.f("ix_products_created_at"), table_name="products")
    op.drop_index(op.f("ix_products_scanned_by_user_id"), table_name="products")
    op.drop_index(op.f("ix_products_confidence_score"), table_name="products")
    op.drop_index(op.f("ix_products_status"), table_name="products")
    op.drop_index(op.f("ix_products_stall_id"), table_name="products")
    op.drop_constraint("fk_products_scanned_by_user_id", "products", type_="foreignkey")

    for column in (
        "scanned_by_user_id",
        "retake_required",
        "image_quality",
        "confidence_score",
        "rule_strength",
        "match_confidence",
        "ocr_confidence",
        "ocr_raw_text",
        "scan_image_path",
        "translation_failed",
        "language_code",
        "explanation_translated",
    ):
        op.drop_column("products", column)

    op.alter_column(
        "products",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "explanation",
        existing_type=sa.Text(),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "ingredients_text",
        existing_type=sa.Text(),
        type_=sa.String(),
        existing_nullable=True,
    )

    op.drop_table("recommendations")
    op.drop_table("ingredient_rules")
    op.drop_table("ingredient_synonyms")
    op.drop_table("ingredients")
