from django.test import TestCase, override_settings

from corehq.apps.translations.models import AITranslationConfig

DEFAULTS = {
    'provider': 'openai',
    'model': 'gpt-4.1',
    'monthly_word_limit': 1_000_000,
}


@override_settings(AI_TRANSLATION_DEFAULTS=DEFAULTS)
class TestAITranslationConfigResolve(TestCase):

    def test_no_rows_returns_settings_defaults(self):
        assert AITranslationConfig.resolve('some-domain', 'fra') == DEFAULTS

    def test_domain_row_overrides_only_set_fields(self):
        AITranslationConfig.objects.create(domain='d', provider='anthropic')
        assert AITranslationConfig.resolve('d', 'fra') == {
            'provider': 'anthropic',
            'model': 'gpt-4.1',
            'monthly_word_limit': 1_000_000,
        }

    def test_domain_lang_row_wins_over_domain_row(self):
        AITranslationConfig.objects.create(domain='d', model='domain-model')
        AITranslationConfig.objects.create(domain='d', lang='fra', model='lang-model')
        assert AITranslationConfig.resolve('d', 'fra')['model'] == 'lang-model'
        assert AITranslationConfig.resolve('d', 'hin')['model'] == 'domain-model'

    def test_blank_fields_in_lang_row_inherit_from_domain_row(self):
        AITranslationConfig.objects.create(domain='d', provider='anthropic', monthly_word_limit=5)
        AITranslationConfig.objects.create(domain='d', lang='fra', model='lang-model')
        assert AITranslationConfig.resolve('d', 'fra') == {
            'provider': 'anthropic',
            'model': 'lang-model',
            'monthly_word_limit': 5,
        }

    def test_other_domains_and_langs_do_not_apply(self):
        AITranslationConfig.objects.create(domain='other', provider='anthropic')
        AITranslationConfig.objects.create(domain='d', lang='hin', provider='anthropic')
        assert AITranslationConfig.resolve('d', 'fra') == DEFAULTS

    def test_zero_word_limit_is_an_override_not_inherited(self):
        AITranslationConfig.objects.create(domain='d', monthly_word_limit=0)
        assert AITranslationConfig.resolve('d', 'fra')['monthly_word_limit'] == 0
