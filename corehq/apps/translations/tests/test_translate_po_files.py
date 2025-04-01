import json
from unittest.mock import MagicMock, patch

from corehq.apps.translations.management.commands.translate_po_files import (
    LLMTranslator,
    OpenaiTranslator,
    TranslationFormat,
)
from corehq.tests.tools import nottest


@nottest
class MockTranslationFormat(TranslationFormat):
    def load_input(self, file_path=None):
        return ["message number 1", "message number 2"]

    def format_input(self, input_data):
        return json.dumps(input_data)

    def parse_output(self, output_data):
        return json.loads(output_data)

    def save_output(self, output_data, output_path):
        return output_path

    def format_input_description(self):
        return "List of messages"

    def format_output_description(self):
        return "List of translated messages"


@nottest
class TestTranslator(LLMTranslator):
    @property
    def supported_models(self):
        return ["test-model"]

    def _call_llm(self, system_prompt, user_message):
        return json.dumps(["Message numero 1", "Message numero 2"])

    def _call_llm_http(self, system_prompt, user_message):
        return json.dumps(["Message numero 1 http", "Message numero 2 http"])


def test_llm_translator_base_prompt():
    translation_format = MockTranslationFormat()
    translator = TestTranslator(
        api_key="test-api-key",
        model="test-model",
        lang="fra",
        translation_format=translation_format
    )

    with patch(
        'corehq.apps.translations.management.commands.translate_po_files.langcode_to_langname_map'
    ) as mock_lang_map:
        mock_lang_map.return_value = {"fra": "French"}
        prompt = translator.base_prompt()
        assert "professional translator" in prompt
        assert "French" in prompt


def test_llm_translator_base_prompt_with_unsupported_lang():
    translation_format = MockTranslationFormat()
    translator = TestTranslator(
        api_key="test-api-key",
        model="test-model",
        lang="some_lang_code",
        translation_format=translation_format
    )

    with patch(
        'corehq.apps.translations.management.commands.translate_po_files.langcode_to_langname_map'
    ) as mock_lang_map:
        mock_lang_map.return_value = {"fra": "French"}
        prompt = translator.base_prompt()
        assert "professional translator" in prompt
        assert "some_lang_code" in prompt


def test_openai_translator_supported_models():
    mock_client = MagicMock()

    translation_format = MockTranslationFormat()
    translator = OpenaiTranslator(
        api_key="test-api-key",
        model="gpt-4",
        lang="es",
        translation_format=translation_format
    )

    with patch.object(translator, 'client') as mock_client:
        mock_client.return_value = mock_client
        models = translator.supported_models
        assert "gpt-4" in models
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models
        assert "gpt-3.5-turbo" in models


def test_openai_translator_call_llm():
    mock_client = MagicMock()

    translation_format = MockTranslationFormat()
    translator = OpenaiTranslator(
        api_key="test-api-key",
        model="gpt-4",
        lang="es",
        translation_format=translation_format
    )
    translator.client = mock_client

    with patch.object(translator, 'client') as mock_client:
        mock_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(["Message numero 1", "Message numero 2"])
        mock_client.chat.completions.create.return_value = mock_response

        result = translator._call_llm("Test prompt", "Test user message")

        assert result == json.dumps(["Message numero 1", "Message numero 2"])
        translator.client.chat.completions.create.assert_called_once()


@patch('corehq.apps.translations.management.commands.translate_po_files.requests.post')
def test_openai_translator_call_llm_http(mock_post):
    translation_format = MockTranslationFormat()
    translator = OpenaiTranslator(
        api_key="test-api-key",
        model="gpt-4",
        lang="es",
        translation_format=translation_format
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(["Message numero 1 http", "Message numero 2 http"])}}]
    }
    mock_post.return_value = mock_response

    result = translator._call_llm_http("Test prompt", "Test user message")

    assert result == json.dumps(["Message numero 1 http", "Message numero 2 http"])
    mock_post.assert_called_once()


@patch('corehq.apps.translations.management.commands.translate_po_files.requests.post')
def test_openai_translator_client_fallback_to_http(mock_post):
    translation_format = MockTranslationFormat()
    translator = OpenaiTranslator(
        api_key="test-api-key",
        model="gpt-4",
        lang="es",
        translation_format=translation_format
    )

    translator.client = None

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(["Message numero 1", "Message numero 2"])}}]
    }
    mock_post.return_value = mock_response

    result = translator._call_llm("Test system prompt", "Test user message")

    assert json.loads(result)[0] == "Message numero 1"
    assert json.loads(result)[1] == "Message numero 2"
    mock_post.assert_called_once()

