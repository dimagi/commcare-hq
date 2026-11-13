from datetime import datetime, timezone

from django.core.cache import cache

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.translations.const import (
    AI_TRANSLATION_LOCK_TIMEOUT,
    AI_TRANSLATION_MAX_RETRIES,
    AI_TRANSLATION_RETRY_DELAY,
)

ACTIVE_STATUS_TIMEOUT = (
    AI_TRANSLATION_MAX_RETRIES * AI_TRANSLATION_RETRY_DELAY
    + AI_TRANSLATION_LOCK_TIMEOUT
)
FINISHED_STATUS_TIMEOUT = 24 * 60 * 60


class AITranslationStatus:
    """
    Status of AI translation runs, one per (app, language), for the
    Languages page to poll.

    A run's status lives under an "active" key while it is queued or
    running. Creating that key is atomic, so a language can't be submitted
    again while its run is active. The key's timeout is the longest a run
    is expected to wait and run. When the run finishes, its summary moves
    to a "finished" key, kept for a day or until the next run starts.
    """
    STATE_QUEUED = 'queued'
    STATE_TRANSLATING = 'translating'
    STATE_APPLYING = 'applying'
    STATE_DONE = 'done'
    STATE_ERROR = 'error'
    ACTIVE_STATES = (STATE_QUEUED, STATE_TRANSLATING, STATE_APPLYING)

    def __init__(self, app_id, lang):
        key = f'ai-app-translation-status-{app_id}-{lang}'
        self._active_key = f'{key}-active'
        self._finished_key = f'{key}-finished'

    def get(self):
        return cache.get(self._active_key) or cache.get(self._finished_key) or {}

    def start(self, username):
        """Queue a run, or return False if one is already active."""
        started = cache.add(self._active_key, {
            'state': self.STATE_QUEUED,
            'username': username,
            'queued_on': json_format_datetime(datetime.now(timezone.utc)),
        }, ACTIVE_STATUS_TIMEOUT)
        if started:
            # if this run is lost, don't show the previous run's summary
            cache.delete(self._finished_key)
        return started

    def update(self, **fields):
        status = cache.get(self._active_key)
        if not status:
            # expired: don't block the language again for another run
            return
        status.update(fields)
        cache.set(self._active_key, status, ACTIVE_STATUS_TIMEOUT)

    def finish(self, state, summary=None, message_code=None):
        """Store the run's final state and summary, and release the
        language for another run. ``message_code`` says why it failed, or
        warns about a run that finished; it is a code so the page can
        show it in the viewer's language."""
        assert state not in self.ACTIVE_STATES, state
        status = cache.get(self._active_key) or {}
        status.update(summary or {})
        status.update({
            'state': state,
            'message_code': message_code,
            'finished_on': json_format_datetime(datetime.now(timezone.utc)),
        })
        cache.set(self._finished_key, status, FINISHED_STATUS_TIMEOUT)
        cache.delete(self._active_key)
