from unittest.mock import patch

from martevi.translation.argos_translator import ArgosTranslator


async def test_translate_delegates_to_argos_with_configured_languages():
    with patch(
        "martevi.translation.argos_translator.argos_translate.translate",
        return_value="Girassóis",
    ) as mock_translate:
        translator = ArgosTranslator("en", "pt")

        result = await translator.translate("Sunflowers")

        assert result == "Girassóis"
        mock_translate.assert_called_once_with("Sunflowers", "en", "pt")


async def test_translate_uses_the_languages_given_at_construction():
    with patch(
        "martevi.translation.argos_translator.argos_translate.translate",
        return_value="sunflowers",
    ) as mock_translate:
        translator = ArgosTranslator("pt", "en")

        await translator.translate("girassóis")

        mock_translate.assert_called_once_with("girassóis", "pt", "en")


async def test_translate_caches_repeated_text_and_only_translates_once():
    with patch(
        "martevi.translation.argos_translator.argos_translate.translate",
        return_value="Girassóis",
    ) as mock_translate:
        translator = ArgosTranslator("en", "pt")

        first = await translator.translate("Sunflowers")
        second = await translator.translate("Sunflowers")

        assert first == second == "Girassóis"
        mock_translate.assert_called_once_with("Sunflowers", "en", "pt")


async def test_translate_cache_is_keyed_on_exact_text():
    with patch(
        "martevi.translation.argos_translator.argos_translate.translate",
        side_effect=["Girassóis", "Retrato"],
    ) as mock_translate:
        translator = ArgosTranslator("en", "pt")

        first = await translator.translate("Sunflowers")
        second = await translator.translate("Portrait")

        assert first == "Girassóis"
        assert second == "Retrato"
        assert mock_translate.call_count == 2


async def test_two_instances_do_not_share_a_cache():
    with patch(
        "martevi.translation.argos_translator.argos_translate.translate",
        return_value="Girassóis",
    ) as mock_translate:
        outbound = ArgosTranslator("en", "pt")
        inbound = ArgosTranslator("pt", "en")

        await outbound.translate("Sunflowers")
        await inbound.translate("Sunflowers")

        assert mock_translate.call_count == 2


async def test_cold_model_is_loaded_by_one_thread_at_a_time():
    """A burst of concurrent first calls must not each build their own model."""
    import asyncio
    import threading
    import time

    from martevi.translation import argos_translator

    lock = threading.Lock()
    calls = 0
    first_running = False
    overlapped_first = False

    def fake_translate(text, source, target):
        nonlocal calls, first_running, overlapped_first
        with lock:
            calls += 1
            is_first = calls == 1
            if is_first:
                first_running = True
            elif first_running:
                overlapped_first = True
        time.sleep(0.05)  # the "model load"
        if is_first:
            with lock:
                first_running = False
        return text.upper()

    argos_translator._loaded.discard(("en", "pt"))
    with patch(
        "martevi.translation.argos_translator.argos_translate.translate",
        side_effect=fake_translate,
    ):
        translator = ArgosTranslator("en", "pt")
        results = await asyncio.gather(*(translator.translate(f"t{i}") for i in range(8)))

    assert results == [f"T{i}" for i in range(8)]
    assert not overlapped_first
