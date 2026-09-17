"""Ingredient-section slicing out of raw OCR text."""

from app.services.products.ingredient_extraction import (
    extract_ingredient_section,
    find_all_anchors,
)

FULL_LABEL = """RAMESH FOODS PVT LTD
Potato Chips - Masala Flavour
Ingredients: Potato, Palm Oil, Refined Wheat Flour (Maida), Salt,
Spices and Condiments, INS 211, Turmeric.
Nutrition Information
Energy 540 kcal
Protein 6 g
Store in a cool dry place. Best before 6 months from packaging.
Net Weight 50 g   MRP Rs 20
"""


class TestExtraction:
    def test_slices_between_anchor_and_terminator(self):
        result = extract_ingredient_section(FULL_LABEL)
        assert result.anchor_found
        assert "Potato" in result.section
        assert "Turmeric" in result.section
        # Must not leak the nutrition table or the manufacturer address.
        assert "540 kcal" not in result.section
        assert "RAMESH FOODS" not in result.section
        assert "Net Weight" not in result.section

    def test_terminator_recorded(self):
        result = extract_ingredient_section(FULL_LABEL)
        assert result.truncated_at is not None
        assert "nutrition" in result.truncated_at.lower()

    def test_missing_anchor_falls_back_to_full_text(self):
        """A label whose heading OCR mangled still has usable ingredient
        text; discarding it would be worse than matching a noisy section."""
        result = extract_ingredient_section("Palm Oil, Salt, Turmeric")
        assert result.anchor_found is False
        assert result.section.strip() == "Palm Oil, Salt, Turmeric"

    def test_devanagari_anchor(self):
        text = "सामग्री: हल्दी, नमक, पाम तेल\nपोषण\nऊर्जा 500"
        result = extract_ingredient_section(text)
        assert result.anchor_found
        assert "हल्दी" in result.section
        assert "ऊर्जा" not in result.section

    def test_short_false_anchor_falls_back(self):
        """"Contains" appears in marketing copy far more often than as a
        heading. A near-empty slice must not be reported as an ingredient
        list."""
        text = "Contains no added sugar. Net Weight 200 g"
        result = extract_ingredient_section(text)
        assert result.anchor_found is False
        assert "no added sugar" in result.section

    def test_empty_input(self):
        result = extract_ingredient_section("")
        assert result.section == ""
        assert result.anchor_found is False
        assert result.is_usable is False

    def test_multiline_section_preserved(self):
        text = "Ingredients: Palm Oil,\nSalt,\nTurmeric\nNutrition Information\nEnergy"
        result = extract_ingredient_section(text)
        assert "Turmeric" in result.section
        assert "Energy" not in result.section

    def test_no_terminator_takes_rest_of_text(self):
        text = "Ingredients: Palm Oil, Salt, Turmeric"
        result = extract_ingredient_section(text)
        assert result.anchor_found
        assert result.truncated_at is None
        assert "Turmeric" in result.section

    def test_find_all_anchors(self):
        anchors = find_all_anchors("Ingredients: a. Contains: b")
        assert len(anchors) >= 2
