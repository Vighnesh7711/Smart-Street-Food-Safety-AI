"""Normalization and label-token parsing."""

import pytest

from app.services.products.normalization import (
    canonicalize_e_number,
    normalize_alias,
    parse_ingredient_section,
    strip_noise,
)


class TestNormalizeAlias:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Palm Oil", "palm oil"),
            ("  PALM   OIL  ", "palm oil"),
            ("Sodium Benzoate", "sodium benzoate"),
            # Hyphens and punctuation collapse to spaces so that
            # "tert-butylhydroquinone" and "tert butylhydroquinone" agree.
            ("tert-butylhydroquinone", "tert butylhydroquinone"),
            # Punctuation is stripped, but *words* are not: normalize_alias is
            # also applied to knowledge-base aliases, so it must never silently
            # drop a token. Removing filler like "contains" is strip_noise's job.
            ("Salt.", "salt"),
            ("(Salt)", "salt"),
            ("Contains: Salt.", "contains salt"),
            ("", ""),
        ],
    )
    def test_basic_forms(self, raw, expected):
        assert normalize_alias(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("INS 211", "e211"),
            ("INS-211", "e211"),
            ("ins211", "e211"),
            ("E211", "e211"),
            ("e 211", "e211"),
            ("(INS 211)", "e211"),
            ("E 102", "e102"),
        ],
    )
    def test_e_numbers_collapse_to_one_form(self, raw, expected):
        assert normalize_alias(raw) == expected

    def test_bare_numbers_are_not_treated_as_e_numbers(self):
        # "211" alone is ambiguous (could be a quantity), so it must not be
        # silently rewritten into a preservative code.
        assert canonicalize_e_number("211") is None

    def test_devanagari_matras_survive(self):
        """Regression: a regex-based `[^\\w\\s]` strip removes matras.

        Devanagari vowel signs are Unicode combining marks (category Mn),
        which `\\w` does not match. Stripping them mangles Hindi and Marathi
        into different, unmatchable strings.
        """
        assert normalize_alias("सामग्री") == "सामग्री"
        assert normalize_alias("हल्दी") == "हल्दी"
        assert normalize_alias("पाम तेल") == "पाम तेल"
        # Must not be silently truncated to its consonant skeleton.
        assert normalize_alias("सामग्री") != "सामगर"

    def test_mixed_script(self):
        assert normalize_alias("हल्दी Turmeric") == "हल्दी turmeric"


class TestStripNoise:
    def test_removes_leading_english_anchor(self):
        assert strip_noise("Ingredients: Refined Wheat Flour") == "Refined Wheat Flour"

    def test_removes_leading_devanagari_anchor(self):
        """Regression: `\\b` cannot match after a Devanagari matra."""
        assert strip_noise("सामग्री: हल्दी") == "हल्दी"
        assert strip_noise("घटक - नमक") == "नमक"

    def test_word_boundaries_prevent_over_stripping(self):
        # "added" must not eat "additive".
        assert "additive" in strip_noise("additive free starch").lower()

    def test_removes_boilerplate(self):
        result = strip_noise("Salt, contains permitted preservatives")
        assert "permitted" not in result.lower()
        assert "salt" in result.lower()


class TestParseIngredientSection:
    def test_splits_and_normalizes(self):
        tokens = parse_ingredient_section("Palm Oil, Salt, Turmeric")
        assert [t.normalized for t in tokens] == ["palm oil", "salt", "turmeric"]

    def test_extracts_percentage_and_strips_it_from_the_token(self):
        tokens = parse_ingredient_section("Sugar (15%), Salt (1.8%)")
        by_name = {t.normalized: t for t in tokens}
        assert by_name["sugar"].percent == 15.0
        assert by_name["salt"].percent == 1.8
        # The digits must not remain in the normalized form, or the token
        # would never match the knowledge base.
        assert "15" not in by_name["sugar"].normalized

    def test_e_number_token_flagged(self):
        tokens = parse_ingredient_section("INS 211")
        assert len(tokens) == 1
        assert tokens[0].normalized == "e211"
        assert tokens[0].is_e_number

    @pytest.mark.parametrize(
        "separator", [",", ";", "•", "|", "/", "\n", " and ", " & "]
    )
    def test_all_separators(self, separator):
        tokens = parse_ingredient_section(f"Palm Oil{separator}Salt")
        assert len(tokens) == 2, f"separator {separator!r} did not split"

    def test_drops_punctuation_and_bare_numbers(self):
        tokens = parse_ingredient_section("Palm Oil, , 15, ., Salt")
        assert [t.normalized for t in tokens] == ["palm oil", "salt"]

    def test_drops_measurement_quantities(self):
        tokens = parse_ingredient_section("Salt 2g, Sugar 100mg")
        assert [t.normalized for t in tokens] == ["salt", "sugar"]

    def test_strips_leading_anchor_from_first_token(self):
        tokens = parse_ingredient_section("Ingredients: Palm Oil, Salt")
        assert tokens[0].normalized == "palm oil"

    def test_devanagari_label(self):
        tokens = parse_ingredient_section("सामग्री: हल्दी, नमक, पाम तेल")
        assert [t.normalized for t in tokens] == ["हल्दी", "नमक", "पाम तेल"]

    def test_empty_input(self):
        assert parse_ingredient_section("") == []
        assert parse_ingredient_section("   ") == []

    def test_positions_are_increasing(self):
        tokens = parse_ingredient_section("Palm Oil, Salt, Turmeric")
        positions = [t.position for t in tokens]
        assert positions == sorted(positions)
