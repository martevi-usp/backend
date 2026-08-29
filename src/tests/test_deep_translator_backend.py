from unittest.mock import MagicMock, patch

from martevi.translation.deep_translator_backend import DeepTranslatorTranslator


async def test_translate_constructs_google_translator_with_configured_languages():
    with patch(
        "martevi.translation.deep_translator_backend.GoogleTranslator"
    ) as mock_google_translator:
        DeepTranslatorTranslator(source="en", target="pt")

        mock_google_translator.assert_called_once_with(source="en", target="pt")


async def test_translate_delegates_to_google_translator():
    with patch(
        "martevi.translation.deep_translator_backend.GoogleTranslator"
    ) as mock_google_translator:
        mock_client = MagicMock()
        mock_client.translate.return_value = "olá"
        mock_google_translator.return_value = mock_client

        translator = DeepTranslatorTranslator(source="en", target="pt")
        result = await translator.translate("hello")

        assert result == "olá"
        mock_client.translate.assert_called_once_with("hello")


async def test_translate_uses_default_source_and_target_languages():
    with patch(
        "martevi.translation.deep_translator_backend.GoogleTranslator"
    ) as mock_google_translator:
        DeepTranslatorTranslator()

        mock_google_translator.assert_called_once_with(source="en", target="pt")
