import uuid
from unittest.mock import patch

import pytest

from dimagi.utils.couch import get_redis_lock, release_lock
from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.celery.tests.utils import run_with_lock_patch
from corehq.apps.translations.app_translations.ai_failed_labels import (
    get_failed_labels,
)
from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)
from corehq.apps.translations.const import MODE_FILL_MISSING
from corehq.apps.translations.exceptions import AppChangedDuringTranslation
from corehq.apps.translations.models import AITranslationConfig
from corehq.apps.translations.tasks import (
    APP_KEPT_CHANGING,
    FAILED,
    NO_LONGER_AVAILABLE,
    NO_STRINGS_TRANSLATED,
    NOT_QUEUED,
    WAITED_TOO_LONG,
    _final_state,
    queue_app_translation,
    run_message,
    translate_app_task,
)
from corehq.blobs.tests.fixtures import blob_db
from corehq.tests.pytest_plugins.patches import suspend

TASKS_PATH = 'corehq.apps.translations.tasks'

DONE = AITranslationStatus.STATE_DONE
ERROR = AITranslationStatus.STATE_ERROR
TRANSLATING = AITranslationStatus.STATE_TRANSLATING
APPLYING = AITranslationStatus.STATE_APPLYING


QUEUED = AITranslationStatus.STATE_QUEUED


def test_queue_app_translation():
    app_id = uuid.uuid4().hex
    with patch.object(translate_app_task, 'delay') as delay:
        assert queue_app_translation(
            'test-domain', app_id, 'fra', MODE_FILL_MISSING, 'user@example.com')
    delay.assert_called_once_with('test-domain', app_id, 'fra', MODE_FILL_MISSING)
    status = AITranslationStatus(app_id, 'fra').get()
    assert status['state'] == QUEUED
    assert status['username'] == 'user@example.com'


def test_queue_app_translation_refuses_while_a_run_is_active():
    app_id = uuid.uuid4().hex
    AITranslationStatus(app_id, 'fra').start('other@example.com')
    with patch.object(translate_app_task, 'delay') as delay:
        assert not queue_app_translation(
            'test-domain', app_id, 'fra', MODE_FILL_MISSING, 'user@example.com')
    delay.assert_not_called()
    assert AITranslationStatus(app_id, 'fra').get()['username'] == 'other@example.com'


def test_queue_app_translation_records_a_failure_to_queue():
    app_id = uuid.uuid4().hex
    with (
        patch.object(translate_app_task, 'delay', side_effect=Exception('Broker is down')),
        pytest.raises(Exception, match='Broker is down'),
    ):
        queue_app_translation(
            'test-domain', app_id, 'fra', MODE_FILL_MISSING, 'user@example.com')
    status = AITranslationStatus(app_id, 'fra')
    assert status.get()['state'] == ERROR
    assert status.get()['message_code'] == NOT_QUEUED
    # the language is released for another run
    assert status.start('user@example.com')


class TestTranslateAppTask(TestCase):

    def setUp(self):
        blob_db()
        self.app = AppFactory(build_version='2.40.0').app
        self.app.save()
        self.addCleanup(self.app.delete)
        self.status = AITranslationStatus(self.app.get_id, 'fra')
        self.status.start('user@example.com')
        enabled = patch(f'{TASKS_PATH}.ai_translation_enabled', return_value=True)
        enabled.start()
        self.addCleanup(enabled.stop)

    def test_successful_run(self):
        states_seen = []

        def fake_run_app_translation(app, target_lang, mode, progress_callback,
                                     **kwargs):
            states_seen.append(self.status.get()['state'])
            # calls _update_progress, which updates the status
            # with the state and the progress
            progress_callback(1, 2)
            states_seen.append(self.status.get()['state'])
            progress_callback(2, 2)
            states_seen.append(self.status.get()['state'])
            return _summary(translated=7, skipped=3)

        with patch(f'{TASKS_PATH}.run_app_translation', fake_run_app_translation):
            self._run_task()

        assert states_seen == [TRANSLATING, TRANSLATING, APPLYING]
        status = self.status.get()
        assert status['state'] == DONE
        assert status['message_code'] is None
        # the summary is kept in the status, with the list's count in its place
        assert (status['total'], status['translated'], status['skipped']) == (10, 7, 3)
        assert status['failed_label_count'] == 0
        assert 'failed_labels' not in status

    def test_failed_labels_are_kept_out_of_the_status(self):
        record = {'reason': 'empty', 'source': 'Name', 'type': 'menu', 'unique_id': 'module-id'}
        summary = {**_summary(translated=9), 'failed_labels': [record]}

        with patch(f'{TASKS_PATH}.run_app_translation', return_value=summary):
            self._run_task()

        status = self.status.get()
        assert 'failed_labels' not in status
        assert status['failed_label_count'] == 1
        assert get_failed_labels(self.app.get_id, 'fra') == [record]

    def test_failing_to_save_the_list_doesnt_fail_the_run(self):
        record = {'reason': 'empty', 'source': 'Name', 'type': 'menu', 'unique_id': 'module-id'}
        summary = {**_summary(translated=9), 'failed_labels': [record]}

        with (
            patch(f'{TASKS_PATH}.run_app_translation', return_value=summary),
            patch(f'{TASKS_PATH}.save_failed_labels', side_effect=Exception('S3 is down')),
            patch(f'{TASKS_PATH}.notify_exception') as notify_exception,
        ):
            self._run_task()

        assert notify_exception.called
        status = self.status.get()
        assert status['state'] == DONE
        assert status['failed_label_count'] == 1

    def test_error_in_the_run(self):
        with (
            patch(f'{TASKS_PATH}.get_app', side_effect=Exception('Couch is down')),
            patch(f'{TASKS_PATH}.notify_exception') as notify_exception,
        ):
            self._run_task()

        assert notify_exception.called
        self._assert_failed_with(FAILED)

    def test_app_changed_during_the_run(self):
        with patch(f'{TASKS_PATH}.run_app_translation',
                   side_effect=AppChangedDuringTranslation):
            self._run_task()

        self._assert_failed_with(APP_KEPT_CHANGING)

    @suspend(run_with_lock_patch)
    def test_run_that_never_gets_the_app_lock(self):
        # another run holds the app's lock, and with no retries the task
        # gives up at once, so the failure hook records the error
        lock = get_redis_lock(f'translate_app_task-{self.app.get_id}:0',
                              timeout=60, name='translate_app_task')
        lock.acquire(blocking=False)
        try:
            with (
                patch.object(translate_app_task, 'max_retries', 0),
                patch(f'{TASKS_PATH}.run_app_translation') as run_app_translation,
            ):
                self._run_task()
        finally:
            release_lock(lock, True)

        assert not run_app_translation.called
        self._assert_failed_with(WAITED_TOO_LONG)

    def test_uses_the_projects_model_config(self):
        AITranslationConfig.objects.create(
            domain=self.app.domain, lang='fra', provider='openai', model='gpt-test')
        with patch(f'{TASKS_PATH}.run_app_translation',
                   return_value=_summary(translated=10)) as run_app_translation:
            self._run_task()

        kwargs = run_app_translation.call_args.kwargs
        assert (kwargs['provider'], kwargs['model']) == ('openai', 'gpt-test')

    def test_run_stops_if_ai_translation_was_turned_off(self):
        with (
            patch(f'{TASKS_PATH}.ai_translation_enabled', return_value=False),
            patch(f'{TASKS_PATH}.run_app_translation') as run_app_translation,
        ):
            self._run_task()

        assert not run_app_translation.called
        self._assert_failed_with(NO_LONGER_AVAILABLE)

    def _run_task(self):
        translate_app_task.apply(
            args=[self.app.domain, self.app.get_id, 'fra', MODE_FILL_MISSING])

    def _assert_failed_with(self, message_code):
        status = self.status.get()
        assert status['state'] == ERROR
        assert status['message_code'] == message_code


@pytest.mark.parametrize('summary, final_state', [
    pytest.param(dict(total=0), (DONE, None), id='nothing-to-translate'),
    pytest.param(dict(translated=9, skipped=1), (DONE, None), id='some-translated'),
    pytest.param(dict(), (ERROR, NO_STRINGS_TRANSLATED), id='every-label-failed'),
    pytest.param(dict(skipped=10), (ERROR, NO_STRINGS_TRANSLATED), id='every-translation-rejected'),
    # the next run translates labels dropped because the app changed
    pytest.param(dict(changed=10), (DONE, None), id='every-label-changed-during-the-run'),
    pytest.param(dict(skipped=1, changed=9), (ERROR, NO_STRINGS_TRANSLATED),
                 id='rest-changed-during-the-run'),
    pytest.param(dict(changed=2), (ERROR, NO_STRINGS_TRANSLATED), id='rest-failed'),
])
def test_final_state(summary, final_state):
    assert _final_state(_summary(**summary)) == final_state


def test_run_message():
    assert run_message(NO_STRINGS_TRANSLATED) == "No labels could be translated."


def test_run_message_without_a_code():
    assert run_message(None) is None


def test_run_message_for_a_code_an_earlier_release_stored():
    # e.g. 'many_skipped', in a status cached before the release that dropped it
    assert run_message('many_skipped') is None


def _summary(total=10, translated=0, skipped=0, changed=0):
    return {
        'total': total,
        'translated': translated,
        'skipped': skipped,
        'changed': changed,
        'failed': total - translated - skipped - changed,
        'app_version': 2,
        'errors': [],
        'failed_labels': [],
    }
