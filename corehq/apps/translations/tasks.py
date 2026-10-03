from functools import partial

from celery.signals import task_failure
from dimagi.utils.logging import notify_exception
from django.utils.translation import gettext as _

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.celery import serial_task
from corehq.apps.celery.locking import CouldNotAcquireLockError
from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)
from corehq.apps.translations.app_translations.ai_translator import (
    ai_translation_enabled,
    run_app_translation,
)
from corehq.apps.translations.const import (
    AI_TRANSLATION_LOCK_TIMEOUT,
    AI_TRANSLATION_MAX_RETRIES,
    AI_TRANSLATION_RETRY_DELAY,
)
from corehq.apps.translations.exceptions import AppChangedDuringTranslation
from corehq.apps.translations.models import AITranslationConfig

HIGH_SKIP_RATE = 0.2


def queue_app_translation(domain, app_id, target_lang, mode, username):
    status = AITranslationStatus(app_id, target_lang)
    if not status.start(username):
        return False
    try:
        translate_app_task.delay(domain, app_id, target_lang, mode)
    except Exception:
        status.finish(AITranslationStatus.STATE_ERROR,
                      error=_("The translation couldn't be queued. Run it again."))
        raise
    return True


@serial_task(
    '{app_id}',
    timeout=AI_TRANSLATION_LOCK_TIMEOUT,
    max_retries=AI_TRANSLATION_MAX_RETRIES,
    default_retry_delay=AI_TRANSLATION_RETRY_DELAY,
)
def translate_app_task(domain, app_id, target_lang, mode):
    """Translate an app into ``target_lang``. Queue it with
    ``queue_app_translation()``."""
    status = AITranslationStatus(app_id, target_lang)
    if not ai_translation_enabled(domain):
        status.finish(AITranslationStatus.STATE_ERROR, error=_(
            "AI translation is no longer available for this project."))
        return
    status.update(state=AITranslationStatus.STATE_TRANSLATING)
    try:
        app = get_app(domain, app_id)
        config = AITranslationConfig.get_model_config(domain, target_lang)
        summary = run_app_translation(
            app, target_lang, mode,
            provider=config['provider'], model=config['model'],
            progress_callback=partial(_update_progress, status),
        )
    except AppChangedDuringTranslation:
        status.finish(AITranslationStatus.STATE_ERROR, error=_(
            "The app kept being saved while the translations were being "
            "applied, so none were saved. Run it again."))
        return
    except Exception:
        notify_exception(None, 'AI app translation failed', details={
            'domain': domain, 'app_id': app_id, 'target_lang': target_lang})
        status.finish(AITranslationStatus.STATE_ERROR, error=_generic_error())
        return
    state, error = _final_state(summary)
    status.finish(state, summary=summary, error=error)


@task_failure.connect(sender=translate_app_task)
def _mark_translation_failed(sender=None, args=None, exception=None, **kwargs):
    """The task body records its own errors. This covers a run that never
    got the app's lock, or failed outside the body. Expects the task to
    be called with positional arguments, as ``queue_app_translation()``
    does."""
    app_id, target_lang = args[1], args[2]
    if isinstance(exception, CouldNotAcquireLockError):
        error = _("Other translations of this app took too long to finish. "
                  "Run it again.")
    else:
        error = _generic_error()
    AITranslationStatus(app_id, target_lang).finish(
        AITranslationStatus.STATE_ERROR, error=error)


def _update_progress(status, batches_done, batches_total):
    if batches_done == batches_total:
        state = AITranslationStatus.STATE_APPLYING
    else:
        state = AITranslationStatus.STATE_TRANSLATING
    status.update(state=state, batches_done=batches_done,
                  batches_total=batches_total)


def _generic_error():
    return _("Something went wrong while translating the app. Review its "
             "translations and run it again.")


def _final_state(summary):
    total = summary['total']
    if not total:
        return AITranslationStatus.STATE_DONE, None
    if summary['failed'] == total:
        return AITranslationStatus.STATE_ERROR, _("No strings could be translated.")

    skipped_rate = summary['skipped'] / total

    if skipped_rate > HIGH_SKIP_RATE:
        return AITranslationStatus.STATE_DONE, _(
            "More than {percent}% of translations failed validation and were "
            "skipped.").format(percent=round(HIGH_SKIP_RATE * 100))
    return AITranslationStatus.STATE_DONE, None
