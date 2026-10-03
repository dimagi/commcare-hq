from django.utils.translation import gettext as _

from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)

HIGH_SKIP_RATE = 0.2

# message codes stored with a run's final status
NO_STRINGS_TRANSLATED = 'no_strings_translated'
MANY_SKIPPED = 'many_skipped'


def run_message(message_code):
    """The text for a run's message code, in the active language."""
    return {
        NO_STRINGS_TRANSLATED: _("No strings could be translated."),
        MANY_SKIPPED: _(
            "More than {percent}% of translations failed validation and were "
            "skipped.").format(percent=round(HIGH_SKIP_RATE * 100)),
    }[message_code]


def _final_state(summary):
    total = summary['total']
    if not total:
        return AITranslationStatus.STATE_DONE, None
    if summary['failed'] == total:
        return AITranslationStatus.STATE_ERROR, NO_STRINGS_TRANSLATED

    skipped_rate = summary['skipped'] / total

    if skipped_rate > HIGH_SKIP_RATE:
        return AITranslationStatus.STATE_DONE, MANY_SKIPPED
    return AITranslationStatus.STATE_DONE, None
