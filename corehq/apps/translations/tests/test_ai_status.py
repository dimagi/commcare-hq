import uuid

import pytest
from django.core.cache import cache

from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)

SUMMARY = {
    'total': 5, 'translated': 3, 'skipped': 1, 'changed': 0, 'failed': 1,
    'app_version': 7, 'errors': [],
}


def test_start_queues_a_run():
    status = _status()
    assert status.start('user@example.com')
    current = status.get()
    assert current['state'] == AITranslationStatus.STATE_QUEUED
    assert current['username'] == 'user@example.com'


def test_start_is_refused_while_a_run_is_active():
    status = _status()
    status.start('first@example.com')
    assert not status.start('second@example.com')
    assert status.get()['username'] == 'first@example.com'


def test_runs_for_other_languages_are_not_blocked():
    app_id = uuid.uuid4().hex
    fra = AITranslationStatus(app_id, 'fra')
    hin = AITranslationStatus(app_id, 'hin')
    fra.start('user@example.com')
    assert hin.start('user@example.com')


def test_update_merges_fields():
    status = _status()
    status.start('user@example.com')
    status.update(state=AITranslationStatus.STATE_TRANSLATING,
                  batches_done=1, batches_total=3)
    status.update(batches_done=2)
    current = status.get()
    assert current['state'] == AITranslationStatus.STATE_TRANSLATING
    assert current['batches_done'] == 2
    assert current['batches_total'] == 3
    assert current['username'] == 'user@example.com'


def test_update_does_not_recreate_an_expired_status():
    status = _status()
    status.start('user@example.com')
    cache.delete(status._active_key)  # as if it expired
    status.update(state=AITranslationStatus.STATE_TRANSLATING)
    assert status.get() == {}
    assert status.start('user@example.com')


def test_finish_stores_summary_and_releases_the_language():
    status = _status()
    status.start('user@example.com')
    status.finish(AITranslationStatus.STATE_DONE,
                  summary=SUMMARY, error='Some strings failed')
    # returns the finished status, not the active one
    current = status.get()
    assert current['state'] == AITranslationStatus.STATE_DONE
    assert current['error'] == 'Some strings failed'
    assert current['username'] == 'user@example.com'
    assert current['finished_on'].endswith('Z')
    assert SUMMARY.items() <= current.items()

    # starting a new run is now allowed
    assert status.start('user@example.com')
    assert status.get()['state'] == AITranslationStatus.STATE_QUEUED


def test_lost_run_does_not_show_the_previous_summary():
    status = _status()
    status.start('user@example.com')
    status.finish(AITranslationStatus.STATE_DONE, summary=SUMMARY)
    status.start('user@example.com')
    cache.delete(status._active_key)  # as if it expired
    assert status.get() == {}


def test_finish_without_an_active_status():
    # e.g. the failure hook after the active status expired
    status = _status()
    status.finish(AITranslationStatus.STATE_ERROR, error='Timed out')
    current = status.get()
    assert current['state'] == AITranslationStatus.STATE_ERROR
    assert current['error'] == 'Timed out'


def test_finish_rejects_an_active_state():
    status = _status()
    with pytest.raises(AssertionError):
        status.finish(AITranslationStatus.STATE_TRANSLATING)


def _status(lang='fra'):
    return AITranslationStatus(uuid.uuid4().hex, lang)
