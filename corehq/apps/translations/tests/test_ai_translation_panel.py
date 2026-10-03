from unittest.mock import patch

from django.test import TestCase

from corehq.apps.app_manager.models import (
    Application,
    LinkedApplication,
    RemoteApp,
)
from corehq.apps.translations.app_translations.ai_panel import (
    get_ai_translation_panel_context,
)
from corehq.apps.translations.models import AITranslationConfig
from corehq.util.test_utils import flag_disabled, flag_enabled

DOMAIN = 'ai-translation-panel'
AI_PANEL = 'corehq.apps.translations.app_translations.ai_panel'


@flag_enabled('AI_APP_TRANSLATION')
@patch(f'{AI_PANEL}.domain_has_privilege', return_value=True)
class TestAITranslationPanelContext(TestCase):

    def test_one_row_per_language_ai_could_translate(self, _):
        app = _make_app(langs=['en', 'fra', 'deu', 'xyz'])

        context = get_ai_translation_panel_context(app)

        assert context['languages'] == [
            {'code': 'fra', 'supported': True, 'last_run': None},
            {'code': 'deu', 'supported': True, 'last_run': None},
            {'code': 'xyz', 'supported': False, 'last_run': None},
        ]
        assert not context['limit_reached']

    def test_monthly_limit_reached(self, _):
        AITranslationConfig.objects.create(domain=DOMAIN, monthly_word_limit=0)

        context = get_ai_translation_panel_context(_make_app(langs=['en', 'fra']))

        assert context['limit_reached']

    def test_without_the_privilege(self, has_privilege):
        has_privilege.return_value = False

        context = get_ai_translation_panel_context(_make_app(langs=['en', 'fra']))

        assert context == {'has_privilege': False, 'is_linked_app': False}

    def test_linked_app(self, _):
        app = LinkedApplication(domain=DOMAIN, name='linked', langs=['en', 'fra'])

        context = get_ai_translation_panel_context(app)

        assert context == {'has_privilege': True, 'is_linked_app': True}

    def test_remote_app_has_no_panel(self, _):
        app = RemoteApp(domain=DOMAIN, name='remote', langs=['en', 'fra'])

        assert get_ai_translation_panel_context(app) is None

    @flag_disabled('AI_APP_TRANSLATION')
    def test_toggle_off(self, _):
        assert get_ai_translation_panel_context(_make_app(langs=['en', 'fra'])) is None


def _make_app(langs):
    app = Application.new_app(DOMAIN, 'Untitled Application')
    app.langs = langs
    return app
