"""Data for the "Translate with AI" panel on an app's Languages page."""
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.dbaccessors import get_latest_build_version
from corehq.apps.translations.app_translations.ai_translator import (
    non_default_langs,
)
from corehq.apps.translations.models import AITranslationUsage


def get_last_ai_runs(app):
    """The last run that saved translations, for each non-default
    language of ``app`` that has one. ``in_version`` is the latest build
    version if that build includes the run, otherwise None."""
    runs = list(
        AITranslationUsage.objects
        .filter(domain=app.domain, app_id=app.get_id, lang__in=non_default_langs(app))
        .order_by('lang', '-created_on', '-pk')
        .distinct('lang')
    )
    if not runs:
        return {}
    latest_build_version = get_latest_build_version(app.domain, app.get_id)
    return {
        run.lang: {
            'strings_attempted': run.strings_attempted,
            'strings_translated': run.strings_translated,
            'total_app_strings': run.total_app_strings,
            'total_app_strings_ai_translated': run.total_app_strings_ai_translated,
            'created_on': json_format_datetime(run.created_on),
            'in_version': (
                latest_build_version
                if latest_build_version is not None and latest_build_version >= run.app_version
                else None
            ),
        }
        for run in runs
    }
