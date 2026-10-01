from django.test import TestCase, override_settings

from corehq.apps.translations.models import AITranslationConfig

DEFAULTS = {
    'provider': 'openai',
    'model': 'gpt-4.1',
    'monthly_word_limit': 1_000_000,
}


@override_settings(AI_TRANSLATION_DEFAULTS=DEFAULTS)
class TestGetMonthlyWordLimit(TestCase):

    def test_no_rows_returns_settings_default(self):
        assert AITranslationConfig.get_monthly_word_limit('d') == 1_000_000

    def test_domain_row_overrides_default(self):
        AITranslationConfig.objects.create(domain='d', monthly_word_limit=5)
        assert AITranslationConfig.get_monthly_word_limit('d') == 5

    def test_domain_row_without_limit_falls_back_to_default(self):
        AITranslationConfig.objects.create(domain='d', provider='anthropic')
        assert AITranslationConfig.get_monthly_word_limit('d') == 1_000_000

    def test_zero_is_an_override_not_inherited(self):
        AITranslationConfig.objects.create(domain='d', monthly_word_limit=0)
        assert AITranslationConfig.get_monthly_word_limit('d') == 0

    def test_other_domains_do_not_apply(self):
        AITranslationConfig.objects.create(domain='other', monthly_word_limit=5)
        assert AITranslationConfig.get_monthly_word_limit('d') == 1_000_000


@override_settings(AI_TRANSLATION_DEFAULTS=DEFAULTS)
class TestGetModelConfig(TestCase):

    def test_no_rows_returns_settings_defaults(self):
        assert AITranslationConfig.get_model_config('d', 'fra') == {
            'provider': 'openai',
            'model': 'gpt-4.1',
        }

    def test_domain_row_overrides_defaults(self):
        AITranslationConfig.objects.create(domain='d', provider='anthropic', model='claude')
        assert AITranslationConfig.get_model_config('d', 'fra') == {
            'provider': 'anthropic',
            'model': 'claude',
        }

    def test_domain_lang_row_wins_over_domain_row(self):
        AITranslationConfig.objects.create(domain='d', provider='p1', model='domain-model')
        AITranslationConfig.objects.create(domain='d', lang='fra', provider='p2', model='lang-model')
        assert AITranslationConfig.get_model_config('d', 'fra') == {
            'provider': 'p2',
            'model': 'lang-model',
        }
        assert AITranslationConfig.get_model_config('d', 'hin') == {
            'provider': 'p1',
            'model': 'domain-model',
        }

    def test_without_lang_uses_domain_row_only(self):
        AITranslationConfig.objects.create(domain='d', provider='p1', model='domain-model')
        AITranslationConfig.objects.create(domain='d', lang='fra', provider='p2', model='lang-model')
        assert AITranslationConfig.get_model_config('d') == {
            'provider': 'p1',
            'model': 'domain-model',
        }

    def test_row_without_model_is_skipped(self):
        AITranslationConfig.objects.create(domain='d', provider='p1', model='domain-model')
        AITranslationConfig.objects.create(domain='d', lang='fra', provider='p2')
        assert AITranslationConfig.get_model_config('d', 'fra') == {
            'provider': 'p1',
            'model': 'domain-model',
        }

    def test_blank_provider_falls_back_to_default(self):
        AITranslationConfig.objects.create(domain='d', model='m')
        assert AITranslationConfig.get_model_config('d', 'fra') == {
            'provider': 'openai',
            'model': 'm',
        }

    def test_other_domains_and_langs_do_not_apply(self):
        AITranslationConfig.objects.create(domain='other', model='m1')
        AITranslationConfig.objects.create(domain='d', lang='hin', model='m2')
        assert AITranslationConfig.get_model_config('d', 'fra') == {
            'provider': 'openai',
            'model': 'gpt-4.1',
        }
