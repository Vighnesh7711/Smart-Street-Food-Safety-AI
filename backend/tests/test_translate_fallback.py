"""Translation client, with emphasis on the graceful-fallback path.

The requirement is that a translation outage must never break a scan. These
tests pin that behaviour: the provider is monkeypatched to fail, and the
caller must still receive usable text plus a flag saying English is being
shown.
"""

import pytest

from app.core.config import settings
from app.integrations import translate_client
from app.integrations.translate_client import translate_many, translate_text


@pytest.fixture(autouse=True)
def _clear_cache():
    """The client caches translations, so tests must not leak into each other."""
    translate_client.clear_cache()
    yield
    translate_client.clear_cache()


@pytest.fixture
def translation_on(monkeypatch):
    monkeypatch.setattr(settings, "SCAN_TRANSLATION_ENABLED", True)


class TestPassthrough:
    def test_english_target_makes_no_provider_call(self, monkeypatch, translation_on):
        def _explode(*args, **kwargs):
            raise AssertionError("provider must not be called for English")

        monkeypatch.setattr(translate_client, "_run_provider", _explode)
        result = translate_text("Palm oil is high in saturated fat.", "en")

        assert result.text == "Palm oil is high in saturated fat."
        assert result.translated is False
        # English is the source language, so this is not a failure and must
        # not trigger the "showing English" banner.
        assert result.warning is None

    def test_disabled_translation_makes_no_provider_call(
        self, monkeypatch, translation_on
    ):
        monkeypatch.setattr(settings, "SCAN_TRANSLATION_ENABLED", False)

        def _explode(*args, **kwargs):
            raise AssertionError("provider must not be called when disabled")

        monkeypatch.setattr(translate_client, "_run_provider", _explode)
        result = translate_text("Some explanation.", "hi")

        assert result.text == "Some explanation."
        assert result.translated is False
        assert result.warning is None

    def test_empty_strings_are_passed_through(self, translation_on):
        result = translate_text("", "hi")
        assert result.text == ""
        assert result.translated is False


class TestSuccessfulTranslation:
    def test_returns_translated_text(self, monkeypatch, translation_on):
        monkeypatch.setattr(
            translate_client,
            "_run_provider",
            lambda texts, target: [f"[{target}] {t}" for t in texts],
        )
        result = translate_text("Palm oil.", "hi")

        assert result.text == "[hi] Palm oil."
        assert result.translated is True
        assert result.warning is None

    def test_batch_sends_one_provider_call(self, monkeypatch, translation_on):
        calls = []

        def _record(texts, target):
            calls.append(list(texts))
            return [f"{target}:{t}" for t in texts]

        monkeypatch.setattr(translate_client, "_run_provider", _record)
        results = translate_many(["one", "two", "three"], "mr")

        assert len(calls) == 1, "uncached strings should batch into one call"
        assert len(calls[0]) == 3
        assert [r.text for r in results] == ["mr:one", "mr:two", "mr:three"]

    def test_result_order_is_preserved(self, monkeypatch, translation_on):
        monkeypatch.setattr(
            translate_client,
            "_run_provider",
            lambda texts, target: [t.upper() for t in texts],
        )
        results = translate_many(["alpha", "beta", "gamma"], "hi")
        assert [r.text for r in results] == ["ALPHA", "BETA", "GAMMA"]


class TestCaching:
    def test_second_call_uses_cache(self, monkeypatch, translation_on):
        calls = []

        def _count(texts, target):
            calls.append(texts)
            return [f"x{t}" for t in texts]

        monkeypatch.setattr(translate_client, "_run_provider", _count)

        translate_text("Repeated explanation.", "hi")
        translate_text("Repeated explanation.", "hi")

        assert len(calls) == 1

    def test_cache_is_per_language(self, monkeypatch, translation_on):
        calls = []

        def _count(texts, target):
            calls.append(target)
            return [f"{target}:{t}" for t in texts]

        monkeypatch.setattr(translate_client, "_run_provider", _count)

        translate_text("Same text.", "hi")
        translate_text("Same text.", "mr")

        assert calls == ["hi", "mr"]

    def test_cache_returns_correct_text(self, monkeypatch, translation_on):
        monkeypatch.setattr(
            translate_client, "_run_provider", lambda texts, target: ["translated"]
        )
        translate_text("original", "hi")
        assert translate_text("original", "hi").text == "translated"


class TestFailureFallback:
    """The core requirement: an outage degrades, it does not break."""

    def test_provider_exception_returns_english_with_warning(
        self, monkeypatch, translation_on
    ):
        def _fail(texts, target):
            raise RuntimeError("translation backend is down")

        monkeypatch.setattr(translate_client, "_run_provider", _fail)
        result = translate_text("Palm oil is high in saturated fat.", "hi")

        assert result.text == "Palm oil is high in saturated fat."
        assert result.translated is False
        assert result.warning is not None
        assert "English" in result.warning

    @pytest.mark.parametrize(
        "error",
        [
            RuntimeError("boom"),
            TimeoutError("timed out"),
            ConnectionError("network unreachable"),
            ValueError("malformed response"),
        ],
    )
    def test_all_exception_types_are_swallowed(
        self, monkeypatch, translation_on, error
    ):
        def _fail(texts, target):
            raise error

        monkeypatch.setattr(translate_client, "_run_provider", _fail)
        # Must not raise, whatever the provider does.
        result = translate_text("Text.", "hi")
        assert result.translated is False
        assert result.text == "Text."

    def test_batch_falls_back_wholesale(self, monkeypatch, translation_on):
        def _fail(texts, target):
            raise RuntimeError("down")

        monkeypatch.setattr(translate_client, "_run_provider", _fail)
        results = translate_many(["one", "two"], "hi")

        assert len(results) == 2
        assert all(r.text in ("one", "two") for r in results)
        assert all(r.translated is False for r in results)
        assert all(r.warning is not None for r in results)

    def test_mismatched_result_count_falls_back(self, monkeypatch, translation_on):
        """A provider returning the wrong number of results must not cause
        texts to be silently paired with the wrong translations."""
        monkeypatch.setattr(
            translate_client, "_run_provider", lambda texts, target: ["only-one"]
        )
        results = translate_many(["one", "two"], "hi")

        assert [r.text for r in results] == ["one", "two"]
        assert all(r.translated is False for r in results)
        assert all(r.warning is not None for r in results)

    def test_failures_are_not_cached(self, monkeypatch, translation_on):
        """A transient outage must not poison the cache with English text."""
        attempts = {"n": 0}

        def _flaky(texts, target):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("temporary")
            return [f"ok:{t}" for t in texts]

        monkeypatch.setattr(translate_client, "_run_provider", _flaky)

        first = translate_text("Text.", "hi")
        assert first.translated is False

        second = translate_text("Text.", "hi")
        assert second.translated is True
        assert second.text == "ok:Text."


class TestProviderConfiguration:
    """Google Cloud Translation was removed in favour of a local model, so
    these replace the old credential-dispatch tests. The contract is the same
    either way: a misconfiguration degrades, it never breaks a scan."""

    def test_indictrans2_is_the_registered_default(self):
        assert settings.TRANSLATION_PROVIDER == "indictrans2"
        assert "indictrans2" in translate_client._PROVIDERS

    def test_unknown_provider_degrades_rather_than_crashing(
        self, monkeypatch, translation_on
    ):
        monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "not_a_provider")
        result = translate_text("Text.", "hi")

        assert result.translated is False
        assert result.text == "Text."
        assert result.warning is not None

    def test_unsupported_language_degrades_with_english(
        self, monkeypatch, translation_on
    ):
        # 'ta' is a real IndicTrans2 tag target but not one this app offers.
        def _explode(*args, **kwargs):
            raise AssertionError("no provider call for an unsupported language")

        monkeypatch.setattr(translate_client, "_run_provider", _explode)
        result = translate_text("Text.", "ta")

        assert result.translated is False
        assert result.text == "Text."
        assert result.warning is not None
        assert "English" in result.warning

    def test_the_configured_provider_is_what_runs(self, monkeypatch, translation_on):
        monkeypatch.setitem(
            translate_client._PROVIDERS,
            "indictrans2",
            lambda texts, target: [f"{target}:{t}" for t in texts],
        )
        result = translate_text("Text.", "hi")

        assert result.translated is True
        assert result.text == "hi:Text."

    def test_no_google_translate_api_key_is_required(self):
        """The whole point of the swap: translation needs no Google credential."""
        assert not hasattr(settings, "GOOGLE_TRANSLATE_API_KEY")
