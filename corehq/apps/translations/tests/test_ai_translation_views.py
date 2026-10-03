from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)
from corehq.apps.translations.models import AITranslationConfig
from corehq.apps.users.models import WebUser

DOMAIN = 'ai-translation-views'
USERNAME = 'translator@example.com'
PASSWORD = 'secret'


class TestStartAITranslation(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        domain = create_domain(DOMAIN)
        cls.addClassCleanup(domain.delete)
        user = WebUser.create(DOMAIN, USERNAME, PASSWORD, None, None, is_admin=True)
        cls.addClassCleanup(user.delete, DOMAIN, deleted_by=None)

    def setUp(self):
        self.app = _make_app(DOMAIN, langs=['en', 'fra', 'hin', 'xyz'])
        self.addCleanup(self.app.delete)
        enabled = patch('corehq.apps.translations.views.ai_translation_enabled',
                        return_value=True)
        self.enabled = enabled.start()
        self.addCleanup(enabled.stop)
        delay = patch('corehq.apps.translations.tasks.translate_app_task.delay')
        self.delay = delay.start()
        self.addCleanup(delay.stop)
        self.client.login(username=USERNAME, password=PASSWORD)

    def test_queues_a_run(self):
        response = self._start('fra')

        assert response.status_code == 200
        self.delay.assert_called_once_with(
            DOMAIN, self.app.get_id, 'fra', 'fill_missing')
        status = AITranslationStatus(self.app.get_id, 'fra').get()
        assert status['state'] == AITranslationStatus.STATE_QUEUED
        assert status['username'] == USERNAME

    def test_other_languages_can_be_queued_while_one_is_queued(self):
        assert self._start('fra').status_code == 200
        assert self._start('hin').status_code == 200

    def test_language_already_queued(self):
        self._start('fra')

        assert self._start('fra').status_code == 409
        assert self.delay.call_count == 1

    def test_languages_that_cant_be_translated(self):
        not_in_app = 'spa'
        default = 'en'
        not_supported = 'xyz'
        for lang in [not_in_app, default, not_supported, None]:
            with self.subTest(lang=lang):
                assert self._start(lang).status_code == 400
        assert not self.delay.called

    def test_ai_translation_not_enabled(self):
        self.enabled.return_value = False

        assert self._start('fra').status_code == 403
        assert not self.delay.called

    def test_monthly_limit_reached(self):
        AITranslationConfig.objects.create(domain=DOMAIN, monthly_word_limit=0)

        assert self._start('fra').status_code == 403
        assert not self.delay.called

    def test_app_build(self):
        build = _make_app(DOMAIN, langs=['en', 'fra'], copy_of=self.app.get_id)
        self.addCleanup(build.delete)

        response = self._start('fra', app_id=build.get_id)

        assert response.status_code == 400
        assert response.json()['error'].startswith('Only the current version')
        assert not self.delay.called

    def test_deleted_app(self):
        self.app.delete_app()
        self.app.save()

        assert self._start('fra').status_code == 404
        assert not self.delay.called

    def test_linked_app(self):
        linked_app = LinkedApplication(
            domain=DOMAIN, name='linked', langs=['en', 'fra'], upstream_app_id='upstream')
        linked_app.save()
        self.addCleanup(linked_app.delete)

        response = self._start('fra', app_id=linked_app.get_id)

        assert response.status_code == 400
        assert response.json()['error'].startswith('Linked apps')
        assert not self.delay.called

    def _start(self, lang, app_id=None):
        url = reverse('start_ai_translation', args=[DOMAIN, app_id or self.app.get_id])
        return self.client.post(url, {'lang': lang} if lang else {})


def _make_app(domain, langs, copy_of=None):
    app = Application.new_app(domain, 'Untitled Application')
    app.langs = langs
    app.copy_of = copy_of
    app.save()
    return app
