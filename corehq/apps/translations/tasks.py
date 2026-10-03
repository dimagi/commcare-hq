from django.utils.translation import gettext as _

from corehq.apps.translations.app_translations.ai_status import (
    AITranslationStatus,
)

HIGH_SKIP_RATE = 0.2


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
