from datetime import datetime

from django.test import TestCase, override_settings
from time_machine import travel

from corehq.apps.translations.app_translations.ai_translator import (
    monthly_word_limit_reached,
)
from corehq.apps.translations.models import (
    AITranslationConfig,
    AITranslationUsage,
)

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


@travel(datetime(2026, 10, 15, 12, 0), tick=False)
class TestMonthlyWordLimitReached(TestCase):

    def setUp(self):
        AITranslationConfig.objects.create(domain='d', monthly_word_limit=1000)

    def test_under_the_limit(self):
        _record_usage('d', words=999)
        assert not monthly_word_limit_reached('d')

    def test_at_the_limit(self):
        _record_usage('d', words=600)
        _record_usage('d', words=400)
        assert monthly_word_limit_reached('d')

    def test_over_the_limit(self):
        # a run can take the project past its limit
        _record_usage('d', words=1001)
        assert monthly_word_limit_reached('d')

    def test_usage_from_the_start_of_the_month_is_counted(self):
        _record_usage('d', words=1000, created_on=datetime(2026, 10, 1, 0, 0))
        assert monthly_word_limit_reached('d')

    def test_last_months_usage_is_not_counted(self):
        _record_usage('d', words=1000, created_on=datetime(2026, 9, 30, 23, 59))
        assert not monthly_word_limit_reached('d')

    def test_other_projects_usage_is_not_counted(self):
        _record_usage('other', words=1000)
        assert not monthly_word_limit_reached('d')


def _record_usage(domain, words, created_on=None):
    usage = AITranslationUsage.objects.create(
        domain=domain, app_id='app', lang='fra', strings_attempted=1,
        words_translated=words, strings_translated=1, total_app_strings=1,
        total_app_strings_ai_translated=1, app_version=1, model='m',
    )
    if created_on:
        # created_on is auto_now_add, so it can't be set on create
        AITranslationUsage.objects.filter(pk=usage.pk).update(created_on=created_on)
