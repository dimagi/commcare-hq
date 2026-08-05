import pytest

from corehq.apps.translations.integrations.llm import language_name


@pytest.mark.parametrize("code, name", [
    ('hin', 'Hindi'),        # 3-letter app language, not in settings.LANGUAGES
    ('en', 'English'),       # grandfathered 2-letter code
    ('xx-nonsense', 'xx-nonsense'),  # unknown falls back to the raw code
])
def test_language_name(code, name):
    assert language_name(code) == name
