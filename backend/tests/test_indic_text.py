"""Text handling for the local IndicTrans2 provider.

No model, no torch, no network -- these run in the default suite. The
model-dependent tests live in test_indictrans2_model.py behind an opt-in
marker.

The two things worth protecting here:
  * the `{src_tag} {tgt_tag} {text}` prefix, which `_src_tokenize` requires and
    parses with `text.split(" ", 2)` -- get it wrong and the tokenizer fails
    inside remote code;
  * sentence splitting, because the model's source cap is 256 tokens and we
    call the tokenizer with `truncation=True`, so a missed split silently
    drops the end of a label.
"""

import pytest

from app.integrations import indic_text
from app.integrations.indic_text import (
    LANGUAGE_TAGS,
    SOURCE_TAG,
    digits_preserved,
    postprocess,
    preprocess,
    split_sentences,
    tag_for,
    validate_tag,
)


class TestLanguageTags:
    def test_app_codes_map_to_flores_codes(self):
        assert tag_for("hi") == "hin_Deva"
        assert tag_for("mr") == "mar_Deva"
        assert tag_for("en") == "eng_Latn"

    def test_case_and_padding_tolerated(self):
        assert tag_for(" HI ") == "hin_Deva"

    def test_unknown_language_returns_default(self):
        assert tag_for("ta") is None
        assert tag_for("ta", "eng_Latn") == "eng_Latn"
        assert tag_for(None) is None
        assert tag_for("") is None

    @pytest.mark.parametrize("tag", ["hin_Deva", "mar_Deva", "eng_Latn"])
    def test_our_tags_are_ones_the_model_knows(self, tag):
        # Guards against a typo that would otherwise fail 4 layers deep, in
        # an AssertionError raised by the model's own tokenizer.
        assert tag in LANGUAGE_TAGS
        assert validate_tag(tag, role="target") == tag

    def test_validate_rejects_unknown_tag(self):
        with pytest.raises(ValueError, match="taml_Deva"):
            validate_tag("taml_Deva", role="target")

    def test_marathi_tag_is_not_the_hindi_one(self):
        # A copy-paste slip here would silently return Hindi for Marathi.
        assert tag_for("mr") != tag_for("hi")


class TestSplitSentences:
    def test_single_sentence(self):
        assert split_sentences("Fat is high.") == ["Fat is high."]

    def test_splits_on_stop_and_keeps_terminator(self):
        assert split_sentences("Fat is high. Add salt.") == [
            "Fat is high.",
            "Add salt.",
        ]

    def test_trailing_text_without_terminator_is_kept(self):
        assert split_sentences("Fat is high. Add salt") == [
            "Fat is high.",
            "Add salt",
        ]

    def test_decimal_number_is_not_a_boundary(self):
        # "32.5" must not become "32." + "5 percent".
        assert split_sentences("Fat is 32.5 percent.") == ["Fat is 32.5 percent."]

    def test_abbreviation_is_not_a_boundary(self):
        assert split_sentences("Additives e.g. colour are listed.") == [
            "Additives e.g. colour are listed."
        ]

    def test_question_and_exclamation_split(self):
        assert split_sentences("Is it safe? Yes! Eat it.") == [
            "Is it safe?",
            "Yes!",
            "Eat it.",
        ]

    def test_devanagari_danda_splits(self):
        assert split_sentences("वसा अधिक है । नमक कम है ।") == [
            "वसा अधिक है ।",
            "नमक कम है ।",
        ]

    def test_empty_and_whitespace_yield_nothing(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []


class TestPreprocess:
    def test_prefixes_source_and_target_tags(self):
        assert preprocess("Fat is high.", "hin_Deva") == [
            "eng_Latn hin_Deva Fat is high."
        ]

    def test_segments_are_one_per_sentence_in_order(self):
        segments = preprocess("Fat is high. Add salt.", "mar_Deva")
        assert segments == [
            "eng_Latn mar_Deva Fat is high.",
            "eng_Latn mar_Deva Add salt.",
        ]

    def test_empty_input_makes_no_segments(self):
        assert preprocess("", "hin_Deva") == []
        assert preprocess("   ", "hin_Deva") == []

    def test_unknown_target_language_raises(self):
        # An app language code is not a tag; passing one is a caller bug.
        with pytest.raises(ValueError):
            preprocess("Fat is high.", "hi")

    def test_unknown_source_language_raises(self):
        with pytest.raises(ValueError):
            preprocess("Fat is high.", "hin_Deva", source_tag="taml_Deva")

    def test_long_text_is_split_under_the_budget(self):
        long_sentence = (
            "This packaged snack contains refined wheat flour, palm oil, "
            "sugar, salt, artificial flavouring agents and permitted "
            "preservatives, and it is manufactured in a facility that also "
            "processes peanuts, tree nuts, milk and soy, so it may not be "
            "suitable for people with allergies."
        )
        segments = preprocess(long_sentence, "hin_Deva", max_chars=80)

        assert len(segments) > 1, "a long single sentence must still be split"
        for segment in segments:
            body = segment.split(" ", 2)[2]
            assert len(body) <= 80, f"segment over budget: {body!r}"

    def test_splitting_does_not_lose_words(self):
        text = "Alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota."
        segments = preprocess(text, "hin_Deva", max_chars=20)
        rejoined = " ".join(s.split(" ", 2)[2] for s in segments)
        for word in ("Alpha", "gamma", "theta", "iota."):
            assert word in rejoined, f"{word} lost in splitting"

    def test_prefix_survives_the_budget_split(self):
        segments = preprocess("a, b, c, d, e, f, g, h, i, j.", "mar_Deva", max_chars=6)
        for segment in segments:
            assert segment.startswith("eng_Latn mar_Deva ")


class TestPostprocess:
    def test_joins_segments(self):
        assert postprocess(["पहला।", "दूसरा।"]) == "पहला। दूसरा।"

    def test_empty_segments_do_not_leave_double_spaces(self):
        assert postprocess(["पहला।", "", "दूसरा।"]) == "पहला। दूसरा।"

    def test_all_empty_yields_empty_string(self):
        assert postprocess([]) == ""
        assert postprocess(["", "   "]) == ""

    def test_collapses_internal_whitespace(self):
        assert postprocess(["बहुत   अधिक"]) == "बहुत अधिक"


class TestDigitsPreserved:
    """The detector that replaced entity masking. See the module docstring."""

    def test_identical_numbers_pass(self):
        assert digits_preserved("32 percent fat", "32 प्रतिशत वसा")

    def test_dropped_number_fails(self):
        assert not digits_preserved("500 mg sodium", "सोडियम")

    def test_changed_number_fails(self):
        # A transposed digit is the dangerous case: the text looks fine.
        assert not digits_preserved("32 percent fat", "23 प्रतिशत वसा")

    def test_multiple_numbers_all_must_survive(self):
        assert digits_preserved("32 fat and 500 sodium", "32 वसा और 500 सोडियम")
        assert not digits_preserved("32 fat and 500 sodium", "32 वसा और 50 सोडियम")

    def test_no_numbers_on_either_side_passes(self):
        assert digits_preserved("Fat is high", "वसा अधिक है")

    def test_number_appearing_from_nowhere_fails(self):
        assert not digits_preserved("Fat is high", "वसा 5 अधिक है")


class TestModuleContract:
    def test_source_tag_is_the_model_canonical_english(self):
        assert SOURCE_TAG == "eng_Latn"
        assert indic_text.tag_for("en") == SOURCE_TAG

    def test_no_entity_masking_survives_in_the_module(self):
        """The masking scheme was removed on measured evidence. If a
        placeholder mechanism comes back, it needs that evidence re-run."""
        assert not hasattr(indic_text, "mask_entities")
        assert not hasattr(indic_text, "unmask_entities")
