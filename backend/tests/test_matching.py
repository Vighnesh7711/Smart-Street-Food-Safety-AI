"""Knowledge-base matching.

These run against the real seeded knowledge base (in SQLite), so they also
verify that the seed data and the matcher agree -- a synonym that normalizes
to something the matcher never produces is a silent failure that only shows
up as a missed ingredient in production.
"""

import pytest

from app.models.enums import MatchMethod
from app.services.products.matching import load_knowledge_base, match_tokens
from app.services.products.normalization import parse_ingredient_section


def _match(label: str, db):
    kb = load_knowledge_base(db)
    return match_tokens(parse_ingredient_section(label), kb)


def _names(matches):
    return {m.ingredient.canonical_name for m in matches}


class TestMatchMethods:
    def test_exact_canonical_name(self, seeded_kb):
        matches = _match("Palm Oil", seeded_kb)
        assert _names(matches) == {"Palm Oil"}
        assert matches[0].method == MatchMethod.EXACT
        assert matches[0].confidence == 1.0

    def test_common_synonym(self, seeded_kb):
        matches = _match("Ajinomoto", seeded_kb)
        assert _names(matches) == {"Monosodium Glutamate"}
        assert matches[0].method == MatchMethod.ALIAS

    def test_ins_number_resolves_to_ingredient(self, seeded_kb):
        matches = _match("INS 211", seeded_kb)
        assert _names(matches) == {"Sodium Benzoate"}
        assert matches[0].method == MatchMethod.E_NUMBER

    def test_e_number_resolves_to_ingredient(self, seeded_kb):
        assert _names(_match("E102", seeded_kb)) == {"Tartrazine"}
        assert _names(_match("E 250", seeded_kb)) == {"Sodium Nitrite"}

    def test_containment_prefers_longest_alias(self, seeded_kb):
        """A label writes the ingredient list, not a synonym.

        "Refined Wheat Flour (Maida)" must resolve to Refined Wheat Flour
        even though "maida" is also an alias for it.
        """
        matches = _match("Refined Wheat Flour (Maida)", seeded_kb)
        assert _names(matches) == {"Refined Wheat Flour"}

    def test_containment_inside_longer_descriptor(self, seeded_kb):
        matches = _match("Partially Hydrogenated Vegetable Oil", seeded_kb)
        assert _names(matches) == {"Hydrogenated Vegetable Oil"}

    def test_vanaspati_is_recognised(self, seeded_kb):
        assert _names(_match("Vanaspati", seeded_kb)) == {
            "Hydrogenated Vegetable Oil"
        }

    def test_fuzzy_recovers_ocr_typo(self, seeded_kb):
        matches = _match("Sodium Benzoatc", seeded_kb)
        assert _names(matches) == {"Sodium Benzoate"}
        assert matches[0].method == MatchMethod.FUZZY
        # A fuzzy match must never be as confident as an exact one.
        assert matches[0].confidence < 1.0

    def test_fuzzy_recovers_transposed_letters(self, seeded_kb):
        assert _names(_match("Tartarzine", seeded_kb)) == {"Tartrazine"}


class TestNoFalsePositives:
    def test_bare_sodium_does_not_match_sodium_benzoate(self, seeded_kb):
        """The failure that would make this tool untrustworthy.

        Substring matching "sodium" against "sodium benzoate" would flag
        almost every label and accuse vendors who have done nothing wrong.
        """
        assert _match("Sodium", seeded_kb) == []

    def test_bare_vegetable_oil_does_not_match_hydrogenated(self, seeded_kb):
        assert _match("Edible Vegetable Oil", seeded_kb) == []

    def test_unknown_ingredient_yields_no_match(self, seeded_kb):
        assert _match("Unobtainium Extract", seeded_kb) == []

    def test_short_tokens_are_not_fuzzy_matched(self, seeded_kb):
        # "malt" is within edit distance of "salt"; fuzzy matching on short
        # tokens produces exactly this kind of noise.
        assert _match("Malt", seeded_kb) == []


class TestLabelLevel:
    def test_full_label(self, seeded_kb):
        label = (
            "Potato, Palm Oil, Refined Wheat Flour (Maida), Salt, "
            "Spices and Condiments, INS 211, Turmeric"
        )
        names = _names(_match(label, seeded_kb))
        assert "Palm Oil" in names
        assert "Refined Wheat Flour" in names
        assert "Sodium Benzoate" in names
        assert "Turmeric" in names

    def test_percentage_propagates_to_match(self, seeded_kb):
        matches = _match("Sugar (15%)", seeded_kb)
        assert matches[0].parsed_percent == 15.0

    def test_duplicate_ingredient_keeps_strongest_match(self, seeded_kb):
        matches = _match("Palm Oil, Refined Palm Oil", seeded_kb)
        palm = [m for m in matches if m.ingredient.canonical_name == "Palm Oil"]
        assert len(palm) == 1
        assert palm[0].confidence == 1.0

    def test_matches_are_ordered_by_position(self, seeded_kb):
        label = "Turmeric, Palm Oil, Salt"
        matches = _match(label, seeded_kb)
        positions = [m.position for m in matches]
        assert positions == sorted(positions)
        assert matches[0].ingredient.canonical_name == "Turmeric"

    def test_devanagari_label_matches(self, seeded_kb):
        """Hindi aliases are seeded for turmeric and salt."""
        matches = _match("हल्दी, नमक", seeded_kb)
        assert _names(matches) == {"Turmeric", "Iodised Salt"}

    def test_empty_label(self, seeded_kb):
        assert _match("", seeded_kb) == []


class TestKnowledgeBase:
    def test_loads_all_seeded_ingredients(self, seeded_kb):
        from app.seeds.seed_data import SEED_INGREDIENTS

        kb = load_knowledge_base(seeded_kb)
        assert len(kb) == len(SEED_INGREDIENTS)

    def test_alias_index_is_not_empty(self, seeded_kb):
        kb = load_knowledge_base(seeded_kb)
        assert len(kb.by_alias) > len(kb)
