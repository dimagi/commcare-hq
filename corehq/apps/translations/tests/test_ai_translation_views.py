from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

import pytest

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.translations.app_translations.ai_failed_labels import (
    failed_label_reason,
    save_failed_labels,
)
from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)
from corehq.apps.translations.app_translations.ai_translator import PROBLEM_EMPTY
from corehq.apps.translations.models import AITranslationConfig
from corehq.apps.translations.tasks import WAITED_TOO_LONG, run_message
from corehq.apps.translations.views import _failed_label_row
from corehq.apps.users.models import WebUser
from corehq.blobs.tests.fixtures import blob_db

DOMAIN = 'ai-translation-views'
USERNAME = 'translator@example.com'
PASSWORD = 'secret'


class AITranslationViewTestCase(TestCase):

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
        self.client.login(username=USERNAME, password=PASSWORD)


class TestStartAITranslation(AITranslationViewTestCase):

    def setUp(self):
        super().setUp()
        delay = patch('corehq.apps.translations.tasks.translate_app_task.delay')
        self.delay = delay.start()
        self.addCleanup(delay.stop)

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


class TestAITranslationStatus(AITranslationViewTestCase):

    def test_returns_the_status_of_each_language_ai_can_translate(self):
        AITranslationStatus(self.app.get_id, 'fra').start(USERNAME)

        response = self._get_status()

        assert response.status_code == 200
        statuses = response.json()
        # not the default language 'en', or 'xyz', which isn't supported
        assert statuses.keys() == {'fra', 'hin'}
        assert statuses['fra']['state'] == AITranslationStatus.STATE_QUEUED
        assert statuses['hin'] == {}

    def test_message_for_a_finished_run(self):
        status = AITranslationStatus(self.app.get_id, 'fra')
        status.start(USERNAME)
        status.finish(AITranslationStatus.STATE_ERROR, message_code=WAITED_TOO_LONG)

        statuses = self._get_status().json()

        assert statuses['fra']['message'] == run_message(WAITED_TOO_LONG)

    def test_ai_translation_not_enabled(self):
        self.enabled.return_value = False

        assert self._get_status().status_code == 403

    def test_app_from_another_project(self):
        # status keys have no project, so this check keeps them private
        other_domain = create_domain('ai-translation-views-other')
        self.addCleanup(other_domain.delete)
        other_app = _make_app(other_domain.name, langs=['en', 'fra'])
        self.addCleanup(other_app.delete)

        assert self._get_status(app_id=other_app.get_id).status_code == 404

    def test_app_build(self):
        build = _make_app(DOMAIN, langs=['en', 'fra'], copy_of=self.app.get_id)
        self.addCleanup(build.delete)

        assert self._get_status(app_id=build.get_id).status_code == 404

    def test_deleted_app(self):
        self.app.delete_app()
        self.app.save()

        assert self._get_status().status_code == 404

    def test_missing_app(self):
        assert self._get_status(app_id='missing').status_code == 404

    def _get_status(self, app_id=None):
        url = reverse('ai_translation_status', args=[DOMAIN, app_id or self.app.get_id])
        return self.client.get(url)


class TestAITranslationFailedLabels(AITranslationViewTestCase):

    def setUp(self):
        super().setUp()
        blob_db()

    def test_returns_the_saved_labels(self):
        record = {'reason': PROBLEM_EMPTY, 'source': 'Register', 'type': 'menu',
                  'unique_id': 'deleted-module'}
        save_failed_labels(DOMAIN, self.app.get_id, 'fra', [record])

        response = self._get_failed_labels('fra')

        assert response.status_code == 200
        assert response.json() == {'labels': [{
            'source': 'Register',
            'reason': failed_label_reason(PROBLEM_EMPTY),
            'location': [],
            'url': None,
        }]}

    def test_no_list(self):
        assert self._get_failed_labels('fra').json() == {'labels': None}

    def test_ai_translation_not_enabled(self):
        self.enabled.return_value = False

        assert self._get_failed_labels('fra').status_code == 403

    def test_app_from_another_project(self):
        other_domain = create_domain('ai-translation-views-other')
        self.addCleanup(other_domain.delete)
        other_app = _make_app(other_domain.name, langs=['en', 'fra'])
        self.addCleanup(other_app.delete)

        assert self._get_failed_labels('fra', app_id=other_app.get_id).status_code == 404

    def _get_failed_labels(self, lang, app_id=None):
        url = reverse('ai_translation_failed_labels', args=[DOMAIN, app_id or self.app.get_id])
        return self.client.get(url, {'lang': lang})


LABELLED_APP_ID = 'labelled-app'
MODULE_ID = 'register_module'  # 'register module'
FORM_ID = 'register_form_0'  # 'register form 0'


def _labelled_app():
    """A menu with a form that has a question, a question and a multiple
    choice question in a group, and two questions where one's id starts
    with the other's."""
    factory = AppFactory(domain=DOMAIN, build_version='2.40.0')
    factory.app._id = LABELLED_APP_ID
    factory.new_basic_module('register', 'case')
    xform = XFormBuilder()
    xform.new_question('name', 'What is the name?')
    household = xform.new_group('household', 'Household')
    household.new_question('head_name', 'Head of household')
    household.new_question('sex', 'Sex', data_type='select', choices={'female': 'Female'})
    xform.new_question('age', 'Age')
    xform.new_question('age-group', 'Age group')
    factory.app.get_module(0).get_form(0).source = xform.tostring().decode('utf-8')
    return factory.app


def _case_property(list_or_detail):
    return {'type': 'case_property', 'unique_id': MODULE_ID,
            'case_property': 'name', 'list_or_detail': list_or_detail}


def _form_text(itext_id):
    return {'type': 'form_text', 'unique_id': FORM_ID, 'itext_id': itext_id}


MENU = ['register module']
FORM = ['register module', 'register form 0']


@pytest.mark.parametrize('record, location, url_name, url_hash', [
    pytest.param({'type': 'menu', 'unique_id': MODULE_ID}, MENU, 'view_module', '', id='menu'),
    pytest.param({'type': 'form', 'unique_id': FORM_ID}, FORM, 'view_form', '', id='form'),
    pytest.param(_case_property('list'), MENU + ['Case list', 'name'], 'view_module', '',
                 id='case-list'),
    pytest.param(_case_property('detail'), MENU + ['Case detail', 'name'], 'view_module', '',
                 id='case-detail'),
    pytest.param(_case_property('case_search_display'), MENU + ['Case search', 'name'],
                 'view_module', '', id='case-search'),
    pytest.param(_form_text('household/head_name-label'), FORM + ['Head of household'],
                 'form_source', '#form/household/head_name', id='question-in-group'),
    pytest.param(_form_text('name-hint'), FORM + ['What is the name? › hint'],
                 'form_source', '#form/name', id='hint'),
    pytest.param(_form_text('household/sex-female-label'), FORM + ['Sex › choice'],
                 'form_source', '#form/household/sex', id='choice'),
    pytest.param(_form_text('age-group-hint'), FORM + ['Age group › hint'],
                 'form_source', '#form/age-group', id='longest-path-wins'),
    pytest.param(_form_text('custom_text'), FORM + ['custom_text'], 'form_source', '',
                 id='not-a-question'),
])
def test_failed_label_row_says_where_the_label_is(record, location, url_name, url_hash):
    record = {'reason': PROBLEM_EMPTY, 'source': 'text', **record}

    row = _failed_label_row(_labelled_app(), record, questions_by_form={})

    assert row['location'] == location
    assert row['url'] == reverse(url_name, args=[DOMAIN, LABELLED_APP_ID, record['unique_id']]) + url_hash


def test_failed_label_row_in_a_form_that_doesnt_parse():
    app = _labelled_app()
    app.get_module(0).get_form(0).source = '<h:html><broken'
    record = {'reason': PROBLEM_EMPTY, 'source': 'text', 'type': 'form_text',
              'unique_id': FORM_ID, 'itext_id': 'name-label'}

    row = _failed_label_row(app, record, questions_by_form={})

    assert row['location'] == ['register module', 'register form 0', 'name-label']
    assert row['url'] == reverse('form_source', args=[DOMAIN, LABELLED_APP_ID, FORM_ID])


@pytest.mark.parametrize('record', [
    pytest.param({'type': 'menu', 'unique_id': 'deleted'}, id='deleted-menu'),
    pytest.param({'type': 'form_text', 'unique_id': 'deleted', 'itext_id': 'name-label'},
                 id='deleted-form'),
])
def test_failed_label_row_for_a_deleted_menu_or_form(record):
    record = {'reason': PROBLEM_EMPTY, 'source': 'text', **record}

    row = _failed_label_row(_labelled_app(), record, questions_by_form={})

    assert (row['location'], row['url']) == ([], None)
    assert row['source'] == 'text'


def _make_app(domain, langs, copy_of=None):
    app = Application.new_app(domain, 'Untitled Application')
    app.langs = langs
    app.copy_of = copy_of
    app.save()
    return app
