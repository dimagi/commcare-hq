"""Data for the "Translate with AI" panel on an app's Languages page."""
from dimagi.utils.parsing import json_format_datetime

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_latest_build_version
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.translations.app_translations.ai_translator import (
    is_supported_language,
    monthly_word_limit_reached,
    non_default_langs,
)
from corehq.apps.translations.models import AITranslationUsage


def get_ai_translation_panel_context(app):
    """Context for the panel, or None if the panel isn't shown."""
    if (not toggles.AI_APP_TRANSLATION.enabled(app.domain, namespace=toggles.NAMESPACE_DOMAIN)
            or app.is_remote_app()):
        return None
    context = {
        'has_privilege': domain_has_privilege(app.domain, privileges.AI_APP_TRANSLATION),
        'is_linked_app': is_linked_app(app),
    }
    if not context['has_privilege'] or context['is_linked_app']:
        return context
    last_runs = get_last_ai_runs(app)
    context.update({
        'limit_reached': monthly_word_limit_reached(app.domain),
        'languages': [
            {
                'code': lang,
                'supported': is_supported_language(lang),
                'last_run': last_runs.get(lang),
            }
            for lang in non_default_langs(app)
        ],
    })
    return context


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
