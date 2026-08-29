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
