import json
from unittest.mock import patch

from corehq.apps.translations.management.commands.translate_po_files import (
    LLMTranslator,
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

    def _call_llm(self, prompt):
        return json.dumps(["Message numero 1", "Message numero 2"])

    def _call_llm_http(self, prompt):
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

