import pytest

from django.test import override_settings

from corehq.apps.translations.integrations.llm import (
    LLMTranslatorError,
    OpenaiTranslator,
    get_llm_translator,
    language_name,
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
