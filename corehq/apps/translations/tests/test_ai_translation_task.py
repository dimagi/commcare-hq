from unittest.mock import patch

from dimagi.utils.couch import get_redis_lock, release_lock
from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.celery.tests.utils import run_with_lock_patch
from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)
from corehq.apps.translations.const import MODE_FILL_MISSING
from corehq.apps.translations.exceptions import AppChangedDuringTranslation
from corehq.apps.translations.models import AITranslationConfig
from corehq.apps.translations.tasks import (
    APP_KEPT_CHANGING,
    FAILED,
    MANY_SKIPPED,
    NO_LONGER_AVAILABLE,
    WAITED_TOO_LONG,
    run_message,
    translate_app_task,
)
from corehq.tests.pytest_plugins.patches import suspend

TASKS_PATH = 'corehq.apps.translations.tasks'

DONE = AITranslationStatus.STATE_DONE
ERROR = AITranslationStatus.STATE_ERROR
TRANSLATING = AITranslationStatus.STATE_TRANSLATING
APPLYING = AITranslationStatus.STATE_APPLYING


class TestTranslateAppTask(TestCase):

    def setUp(self):
        self.app = AppFactory(build_version='2.40.0').app
        self.app.save()
        self.addCleanup(self.app.delete)
        self.status = AITranslationStatus(self.app.get_id, 'fra')
        self.status.start('user@example.com')
        enabled = patch(f'{TASKS_PATH}.ai_translation_enabled', return_value=True)
        enabled.start()
        self.addCleanup(enabled.stop)

    def test_successful_run(self):
        summary = _summary(translated=7, skipped=3)
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
            return summary

        with patch(f'{TASKS_PATH}.run_app_translation', fake_run_app_translation):
            self._run_task()

        assert states_seen == [TRANSLATING, TRANSLATING, APPLYING]
        status = self.status.get()
        assert status['state'] == DONE
        assert status['message_code'] == MANY_SKIPPED
        assert summary.items() <= status.items()

    def test_no_skip_warning_for_a_small_run(self):
        with patch(f'{TASKS_PATH}.run_app_translation',
                   return_value=_summary(total=1, skipped=1)):
            self._run_task()

        status = self.status.get()
        assert status['state'] == DONE
        assert status['message_code'] is None

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


def test_run_message():
    assert run_message(MANY_SKIPPED) == (
        "More than 20% of translations failed validation and were skipped.")


def test_run_message_without_a_code():
    assert run_message(None) is None


def _summary(total=10, translated=0, skipped=0, changed=0):
    return {
        'total': total,
        'translated': translated,
        'skipped': skipped,
        'changed': changed,
        'failed': total - translated - skipped - changed,
        'app_version': 2,
        'errors': [],
    }
