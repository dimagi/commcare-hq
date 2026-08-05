from unittest.mock import MagicMock, patch

import pytest

from django.test import override_settings

from corehq.apps.translations.integrations.llm import (
    LLMTranslatorError,
    OpenaiTranslator,
    SingleStringFormat,
    get_llm_translator,
    language_name,
    translate_string,
)


@pytest.mark.parametrize("code, name", [
    ('hin', 'Hindi'),        # 3-letter app language, not in settings.LANGUAGES
    ('en', 'English'),       # grandfathered 2-letter code
    ('xx-nonsense', 'xx-nonsense'),  # unknown falls back to the raw code
])
def test_language_name(code, name):
    assert language_name(code) == name


def test_get_llm_translator_returns_openai():
    translator = get_llm_translator('hin', translation_format=None, api_key='sk-test')
    assert isinstance(translator, OpenaiTranslator)
    assert translator.model == 'gpt-4.1'
    assert translator.backup_model == 'gpt-4o'


@override_settings(AI_TRANSLATION_API_KEYS={'openai': 'sk-from-settings'})
def test_get_llm_translator_reads_key_from_settings():
    translator = get_llm_translator('hin', translation_format=None)
    assert translator.api_key == 'sk-from-settings'


def test_get_llm_translator_unknown_provider():
    with pytest.raises(LLMTranslatorError):
        get_llm_translator('hin', None, provider='acme', api_key='sk-test')


@override_settings(AI_TRANSLATION_API_KEYS={'openai': ''})
def test_get_llm_translator_missing_api_key():
    with pytest.raises(LLMTranslatorError):
        get_llm_translator('hin', None)


def test_single_string_format_round_trip():
    fmt = SingleStringFormat()
    assert fmt.format_input("Hello <output value=\"/data/name\"/>") == (
        '{"0": "Hello <output value=\\"/data/name\\"/>"}')
    assert fmt.parse_output('{"0": "Bonjour"}') == "Bonjour"
    assert fmt.parse_output('not json') == ""
    assert fmt.parse_output('{"1": "wrong key"}') == ""


def test_translate_string_calls_translator():
    fake_translator = MagicMock()
    fake_translator.translate.return_value = "नमस्ते"
    with patch(
        'corehq.apps.translations.integrations.llm.get_llm_translator',
        return_value=fake_translator,
    ) as factory:
        assert translate_string("Hello", "hin") == "नमस्ते"
    factory.assert_called_once()
    fake_translator.translate.assert_called_once_with("Hello")


def test_openai_payload_uses_json_schema_mode():
    translator = get_llm_translator('hin', translation_format=None, api_key='sk-test')
    assert translator._response_format() == {
        "type": "json_schema",
        "json_schema": {
            "name": "translations",
            "strict": False,
            "schema": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
    }


@patch('corehq.apps.translations.integrations.llm.requests.post')
def test_http_path_uses_json_schema_with_json_object_fallback(mock_post):
    translator = get_llm_translator('hin', translation_format=None, api_key='sk-test')
    schema_rejected = MagicMock(status_code=400)
    accepted = MagicMock(status_code=200)
    accepted.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
    mock_post.side_effect = [schema_rejected, accepted]

    assert translator._call_llm_http('sys', 'user') == "{}"

    first, second = (c.kwargs['json'] for c in mock_post.call_args_list)
    assert first['response_format'] == translator._response_format()
    assert second['response_format'] == {"type": "json_object"}
