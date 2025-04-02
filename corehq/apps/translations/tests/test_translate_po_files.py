import json
from unittest.mock import MagicMock, patch

from corehq.apps.translations.management.commands.translate_po_files import (
    LLMTranslator,
    OpenaiTranslator,
    PoTranslationFormat,
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


class TestPoTranslationFormat:

    def test_init(self):
        po_format = PoTranslationFormat("test_file.po")
        assert po_format.file_path == "test_file.po"
        assert po_format.translation_obj_map == {}

    def test_untranslated_messages(self):
        po_format = PoTranslationFormat("test_file.po")
        mock_entry1 = MagicMock(msgid="Hello", msgstr="")
        mock_entry2 = MagicMock(msgid="World", msgstr="Mundo")
        po_format.all_message_objects = [mock_entry1, mock_entry2]

        result = po_format.untranslated_messages

        assert len(result) == 1
        assert result[0] == mock_entry1

    def test_untranslated_messages_plural(self):
        po_format = PoTranslationFormat("test_file.po")
        mock_entry1 = MagicMock(msgid="One item", msgid_plural="Many items", msgstr_plural={0: ""})
        mock_entry2 = MagicMock(msgid="One world", msgid_plural="Many worlds", msgstr_plural={0: "Un mundo"})
        po_format.all_message_objects = [mock_entry1, mock_entry2]

        result = po_format.untranslated_messages_plural

        assert len(result) == 1
        assert result[0] == mock_entry1

    def test_build_translation_obj_map(self):
        po_format = PoTranslationFormat("test_file.po")
        mock_entry1 = MagicMock(msgid="Hello", msgstr="")
        mock_entry2 = MagicMock(msgid="World", msgstr="")
        translations = [mock_entry1, mock_entry2]

        po_format.load_input(translations)

        assert po_format.translation_obj_map == {"0": mock_entry1, "1": mock_entry2}

    def test_format_input(self):
        po_format = PoTranslationFormat("test_file.po")
        mock_entry1 = MagicMock(msgid="Hello", msgstr="")
        mock_entry2 = MagicMock(msgid="World", msgstr="")
        msg_id_batch = {"0": mock_entry1, "1": mock_entry2}

        result = po_format.format_input(msg_id_batch)

        assert result == json.dumps({"0": "Hello", "1": "World"})

    def test_create_batches(self):
        po_format = PoTranslationFormat("test_file.po")
        mock_entry1 = MagicMock(msgid="Hello", msgstr="")
        mock_entry2 = MagicMock(msgid="World", msgstr="")
        mock_entry3 = MagicMock(msgid="Test", msgstr="")
        input_data = [mock_entry1, mock_entry2, mock_entry3]

        result = po_format.create_batches(input_data, batch_size=2)

        assert len(result) == 2
        assert result[0] == {"0": mock_entry1, "1": mock_entry2}
        assert result[1] == {"2": mock_entry3}

    def test_parse_output_valid_json(self):
        po_format = PoTranslationFormat("test_file.po")
        output_data = json.dumps({"0": "Hola", "1": "Mundo"})
        po_format.translation_obj_map = {
            "0": MagicMock(msgid="Hello", msgstr=""),
            "1": MagicMock(msgid="World", msgstr="")
        }
        result = po_format.parse_output(output_data)

        assert result == {"0": "Hola", "1": "Mundo"}

    def test_parse_output_invalid_json(self):
        po_format = PoTranslationFormat("test_file.po")
        output_data = "invalid json"

        result = po_format.parse_output(output_data)

        assert result == {}

    def test_fill_translations(self):
        po_format = PoTranslationFormat("test_file.po")
        mock_entry1 = MagicMock(msgid="Hello", msgstr="")
        mock_entry2 = MagicMock(msgid="World", msgstr="")
        po_format.translation_obj_map = {"0": mock_entry1, "1": mock_entry2}

        llm_output = {"0": "Hola", "1": "Mundo"}
        po_format.fill_translations(llm_output)

        assert mock_entry1.msgstr == "Hola"
        assert mock_entry2.msgstr == "Mundo"

    @patch('corehq.apps.translations.management.commands.translate_po_files.polib.pofile')
    def test_save_output(self, mock_pofile):
        po_format = PoTranslationFormat("test_file.po")
        mock_po_file = MagicMock()
        po_format.all_message_objects = mock_po_file

        po_format.save_output()

        mock_po_file.save.assert_called_once()

    def test_format_input_description(self):
        po_format = PoTranslationFormat("test_file.po")
        result = po_format.format_input_description()

        assert "Ensure that translations are gender neutral" in result
        assert "Input: JSON array of objects" in result
        assert "Special characters like double quotes" in result

    def test_format_output_description(self):
        po_format = PoTranslationFormat("test_file.po")
        result = po_format.format_output_description()

        assert "Response: JSON object" in result

    def test_is_valid_msgstr(self):
        # Test valid msgstr
        assert PoTranslationFormat._is_valid_msgstr("Hello", "Hola")

        # Test invalid msgstr with unescaped quotes
        assert not PoTranslationFormat._is_valid_msgstr("Hello", 'Hola"')

        # Test invalid msgstr with unescaped backslashes
        assert not PoTranslationFormat._is_valid_msgstr("Hello", "Hola\\")

        # Test invalid msgstr with mismatched placeholders
        assert not PoTranslationFormat._is_valid_msgstr("Hello %s", "Hola %d")

        # Test invalid msgstr with unescaped newlines
        assert not PoTranslationFormat._is_valid_msgstr("Hello", "Hola\n")


@patch('corehq.apps.translations.management.commands.translate_po_files.polib')
def test_end_to_end_flow(mock_polib):
    mock_entry1 = MagicMock(msgid="Hello", msgstr="")
    mock_entry2 = MagicMock(msgid="World", msgstr="")
    mock_po_file = MagicMock()
    mock_po_file.__iter__.return_value = [mock_entry1, mock_entry2]
    mock_polib.pofile.return_value = mock_po_file

    translation_format = PoTranslationFormat("test_file.po")
    translator = OpenaiTranslator(
        api_key="test-api-key",
        model="gpt-4",
        lang="es",
        translation_format=translation_format
    )

    with patch.object(translator, 'client') as mock_client:
        mock_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"0": "Hola", "1": "Mundo"})
        mock_client.chat.completions.create.return_value = mock_response

        to_be_translated = translation_format.create_batches(batch_size=2)
        translation = translator.translate(to_be_translated[0])

        assert translation == {"0": "Hola", "1": "Mundo"}
