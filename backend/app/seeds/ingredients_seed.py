"""Idempotent seed for the ingredient knowledge base.

Run with:

    python -m app.seeds.ingredients_seed

Re-running is safe and is the intended way to apply edits to seed_data.py:
rows are matched on `canonical_name`, so an existing ingredient is updated
in place (and its synonyms and rules rebuilt) rather than duplicated. A
product_ingredients row that references an ingredient therefore survives a
re-seed, which matters because those rows are scan history.

Destructive only in one respect: synonyms and rules for a *seeded*
ingredient are replaced wholesale, so manual edits to the rules of a seeded
ingredient will be overwritten. Ingredients not present in seed_data.py are
left untouched.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import ScanStatus
from app.models.ingredient import Ingredient, IngredientSynonym
from app.models.ingredient_rule import IngredientRule, Recommendation
from app.seeds.seed_data import SEED_INGREDIENTS, IngredientSeed
from app.services.products.normalization import normalize_alias

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed")


def _apply_ingredient(db: Session, seed: IngredientSeed) -> tuple[Ingredient, bool]:
    """Create or update one ingredient. Returns (ingredient, created)."""
    ingredient = (
        db.query(Ingredient)
        .filter(Ingredient.canonical_name == seed.canonical_name)
        .first()
    )
    created = ingredient is None
    if created:
        ingredient = Ingredient(canonical_name=seed.canonical_name)
        db.add(ingredient)

    # All NOT NULL columns are assigned *before* the first flush. Flushing
    # immediately after `db.add` would emit the INSERT with category and
    # default_risk_level still unset, violating their NOT NULL constraints.
    ingredient.category = seed.category.value
    ingredient.default_risk_level = seed.risk.value
    ingredient.description = seed.description
    ingredient.is_active = True
    db.flush()

    # Rebuild synonyms. The unique constraint on normalized_alias means a
    # stale row would block a legitimate re-assignment, so clear first.
    db.query(IngredientSynonym).filter(
        IngredientSynonym.ingredient_id == ingredient.id
    ).delete(synchronize_session=False)
    db.flush()

    seen_aliases: set[str] = set()
    candidates = [(seed.canonical_name, "common_name")] + [
        (syn.alias, syn.alias_type.value) for syn in seed.synonyms
    ]
    for alias, alias_type in candidates:
        normalized = normalize_alias(alias)
        if not normalized or normalized in seen_aliases:
            continue
        seen_aliases.add(normalized)
        db.add(
            IngredientSynonym(
                ingredient_id=ingredient.id,
                alias=alias,
                normalized_alias=normalized,
                alias_type=alias_type,
            )
        )
    db.flush()

    # Rebuild the rule (one per seeded ingredient).
    db.query(IngredientRule).filter(
        IngredientRule.ingredient_id == ingredient.id
    ).delete(synchronize_session=False)
    db.flush()

    if seed.rule is not None:
        rule = IngredientRule(
            ingredient_id=ingredient.id,
            rule_type=seed.rule.rule_type.value,
            conditions=seed.rule.conditions,
            severity=seed.risk.value,
            status_on_match=seed.rule.status.value,
            explanation_template=seed.rule.template,
            is_active=True,
        )
        db.add(rule)
        db.flush()

        for rec in seed.recommendations:
            db.add(
                Recommendation(
                    rule_id=rule.id,
                    ingredient_id=ingredient.id,
                    title=rec.title,
                    body=rec.body,
                    priority=rec.priority,
                    is_active=True,
                )
            )

    return ingredient, created


def seed(db: Session) -> tuple[int, int]:
    created_count = 0
    updated_count = 0

    for item in SEED_INGREDIENTS:
        _, created = _apply_ingredient(db, item)
        if created:
            created_count += 1
        else:
            updated_count += 1

    db.commit()
    return created_count, updated_count


def _validate() -> list[str]:
    """Catch seed-data mistakes before touching the database.

    The status on a rule has to be one of the five, and a category
    restriction without an allowed_categories list would silently never
    fire -- both are cheap to catch here and expensive to notice later.
    """
    problems: list[str] = []
    valid_statuses = {s.value for s in ScanStatus}
    seen_names: set[str] = set()

    for item in SEED_INGREDIENTS:
        if item.canonical_name in seen_names:
            problems.append(f"duplicate canonical_name: {item.canonical_name}")
        seen_names.add(item.canonical_name)

        if item.rule is None:
            continue

        if item.rule.status.value not in valid_statuses:
            problems.append(
                f"{item.canonical_name}: invalid status {item.rule.status.value!r}"
            )

        if item.rule.rule_type.value == "category_restriction":
            allowed = item.rule.conditions.get("allowed_categories")
            if not allowed:
                problems.append(
                    f"{item.canonical_name}: category_restriction with no allowed_categories"
                )

        if item.rule.rule_type.value == "threshold":
            if "max_pct" not in item.rule.conditions:
                problems.append(
                    f"{item.canonical_name}: threshold rule with no max_pct"
                )

    # normalized aliases must be globally unique.
    alias_owner: dict[str, str] = {}
    for item in SEED_INGREDIENTS:
        aliases = [item.canonical_name] + [s.alias for s in item.synonyms]
        for alias in aliases:
            normalized = normalize_alias(alias)
            if not normalized:
                problems.append(f"{item.canonical_name}: alias {alias!r} normalizes to empty")
                continue
            previous = alias_owner.get(normalized)
            if previous and previous != item.canonical_name:
                problems.append(
                    f"alias {alias!r} ({normalized!r}) claimed by both "
                    f"{previous!r} and {item.canonical_name!r}"
                )
            alias_owner[normalized] = item.canonical_name

    return problems


def main() -> int:
    problems = _validate()
    if problems:
        logger.error("Seed data has %d problem(s):", len(problems))
        for problem in problems:
            logger.error("  - %s", problem)
        return 1

    db = SessionLocal()
    try:
        created, updated = seed(db)
    finally:
        db.close()

    with_rule = sum(1 for i in SEED_INGREDIENTS if i.rule is not None)
    logger.info(
        "Seeded %d ingredients (%d created, %d updated); %d carry a rule, "
        "%d are rule-free.",
        len(SEED_INGREDIENTS),
        created,
        updated,
        with_rule,
        len(SEED_INGREDIENTS) - with_rule,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
