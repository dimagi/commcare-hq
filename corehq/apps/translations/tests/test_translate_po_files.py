import json
import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import polib
import pytest

from corehq.apps.translations.management.commands.translate_po_files import (
    LLMTranslator,
    OpenaiTranslator,
    PoTranslationFormat,
    TranslationFormat,
)
from corehq.tests.tools import nottest


@nottest
class MockTranslationFormat(TranslationFormat):
    def load_input(self, input_source=None):
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
        assert "gpt-4.1" in models


def test_openai_translator_call_llm():
    mock_client = MagicMock()
    mock_openai = MagicMock()
    mock_openai.RateLimitError = Exception

    translation_format = MockTranslationFormat()
    translator = OpenaiTranslator(
        api_key="test-api-key",
        model="gpt-4",
        lang="es",
        translation_format=translation_format
    )
    translator.client = mock_client
    translator.openai = mock_openai

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

    @pytest.mark.parametrize("msgid, msgstr", [
        ("Hello", "Hola"),  # Basic valid msgstr
        ('Hello "world"', 'Hola "mundo"'),  # msgstr with double quotes
        ("Hello \\n", "Hola \\n"),  # msgstr with backslash
        ("Hello %s", "Hola %s"),  # msgstr with placeholder
        ("Hello %(name)s", "Hola %(name)s"),  # msgstr with named placeholder
        ("Hello {name}", "Hola {name}"),  # msgstr with named placeholder
        ("<a>Hello</a>", "<a>Hola</a>"),  # msgstr with HTML tag
        ('<a href="test">Hello</a>', '<a href="test">Hola</a>'),  # msgstr with HTML tag and attribute
        ("<br/>", "<br/>"),  # msgstr with single HTML closing tag
        ("Visit https://example.com", "Visita https://example.com"),  # msgstr with URL
        ("Visit www.example.com", "Visita www.example.com"),  # msgstr with URL without protocol
        ("Hello\nWorld", "Hola\nMundo"),  # msgstr with newline
        ("Hello\nWorld", "Hola\n Mundo"),  # msgstr with newline and space
        ('"Hola\n Mundo"', '"Hola\n Mundo"'),  # msgstr with newline and space
        ("Hello &amp; World", "Hola &amp; Mundo"),  # msgstr with HTML entity
        ("Hello &amp; World", "Hola et Mundo"),  # msgstr with HTML entity but msgid is not
        ("Hello ", "Hola "),  # msgstr preserves whitespace
        ("  Hello  ", "  Hola  "),  # msgstr preserves whitespace
    ])
    def test_is_valid_msgstr(self, msgid, msgstr):
        assert PoTranslationFormat.is_valid_msgstr(msgid, msgstr)

    @pytest.mark.parametrize("msgid, msgstr", [
        ("Hello %(name)s", "Hola %(nombre)s"),  # Different named placeholder
        ("Hello {name}", "Hola {nombre}"),  # Different named placeholder
        ("Hello %s", "Hola"),  # Missing placeholder
        ("Visit https://example.com", "Visita https://different.com"),  # Different URL
        ("Visit www.example.com", "Visita www.different.com"),  # Different URL
        ("<a>Hello</a>", "<b>Hola</b>"),  # Different tags
        ("<a>Hello</a>", "<a>Hola"),  # Missing tags
        ("<a>Hello</a>", "Hola"),  # Missing tags
    ])
    def test_is_valid_msgstr_invalid(self, msgid, msgstr):
        assert not PoTranslationFormat.is_valid_msgstr(msgid, msgstr)


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
    translator.openai = MagicMock()
    translator.openai.RateLimitError = Exception

    with patch.object(translator, 'client') as mock_client:
        mock_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"0": "Hola", "1": "Mundo"})
        mock_client.chat.completions.create.return_value = mock_response

        to_be_translated = translation_format.create_batches(batch_size=2)
        translation = translator.translate(to_be_translated[0])

        assert translation == {"0": "Hola", "1": "Mundo"}


def test_extract_errored_msgstr_ids():
    po_format = PoTranslationFormat("dummy.po")
    error_output = (
        "dummy.po:10: some error message\n"
        "dummy.po:15: warning: some warning message\n"
        "dummy.po:20: another error message\n"
        "dummy.po:25: yet another error message :with a reason\n"
    )
    result = po_format._extract_errored_msgstr_ids(error_output)
    assert 10 in result
    assert 20 in result
    assert 25 in result
    assert 15 not in result
    assert result[10] == "some error message"
    assert result[20] == "another error message"
    assert result[25] == "yet another error message : with a reason"


def test_run_msgfmt_returns_stderr():
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write('msgid "Hello"\nmsgstr "Hola"\n')
        tmp_path = tmp.name
    po_format = PoTranslationFormat(tmp_path)
    fake_stderr = "fake error output"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["msgfmt", "--check", "-o", "/dev/null", tmp_path],
            returncode=1,
            stdout="",
            stderr=fake_stderr
        )
        result = po_format._run_msgfmt(tmp_path)
        assert result == fake_stderr
    os.remove(tmp_path)


def test_remove_errored_translations():

    po_content = (
        'msgid "A"\n'
        'msgstr "a"\n\n'
        'msgid "B"\n'
        'msgstr "b"\n\n'
        'msgid "C"\n'
        'msgstr "c"\n'
    )
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".po") as tmp:
        tmp.write(po_content)
        po_file_path = tmp.name

    # Find the line numbers of each msgstr in the file
    msgstr_lines = []
    with open(po_file_path) as f:
        for i, line in enumerate(f, 1):
            if line.startswith('msgstr'):
                msgstr_lines.append(i)

    line_num_error_map = {
        msgstr_lines[1]: "error at B",
        msgstr_lines[2]: "error at C"
    }

    po_format = PoTranslationFormat(po_file_path)
    with patch("corehq.apps.translations.management.commands.translate_po_files.polib.pofile", wraps=polib.pofile):
        po_format._remove_errored_translations(line_num_error_map)

    updated_po = polib.pofile(po_file_path)
    assert updated_po[0].msgstr == "a"
    assert updated_po[1].msgstr == ""
    assert updated_po[2].msgstr == ""
    os.remove(po_file_path)
