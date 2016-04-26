import collections
from corehq import privileges, toggles
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY
from django_prbac.utils import has_privilege


def localize(value, lang):
    """
    Localize the given value.

    This function is intended to be used within UCR to localize user supplied
    translations.

    :param value: A dict-like object or string
    :param lang: A language code.
    """
    if isinstance(value, collections.Mapping) and len(value):
        return (
            value.get(lang, None) or
            value.get(default_language(), None) or
            value[sorted(value.keys())[0]]
        )
    return value


def default_language():
    return "en"


def has_report_builder_access(request):
    report_builder_add_on_privs = {
        privileges.REPORT_BUILDER_TRIAL,
        privileges.REPORT_BUILDER_5,
        privileges.REPORT_BUILDER_15,
        privileges.REPORT_BUILDER_30,
    }
    builder_enabled = toggle_enabled(request, toggles.REPORT_BUILDER)
    legacy_builder_priv = has_privilege(request, privileges.REPORT_BUILDER)
    beta_group_enabled = toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)
    has_add_on_priv = any(toggle_enabled(p) for p in report_builder_add_on_privs)

    return (builder_enabled and legacy_builder_priv) or beta_group_enabled or has_add_on_priv


def add_event(request, event):
    events = request.session.get(REPORT_BUILDER_EVENTS_KEY, [])
    request.session[REPORT_BUILDER_EVENTS_KEY] = events + [event]
