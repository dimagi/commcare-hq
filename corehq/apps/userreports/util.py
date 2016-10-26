import collections
import hashlib

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from corehq.util.soft_assert import soft_assert
from corehq import privileges, toggles
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.userreports.const import (
    REPORT_BUILDER_EVENTS_KEY,
    UCR_ES_BACKEND
)
from django_prbac.utils import has_privilege

from corehq.apps.userreports.dbaccessors import get_all_es_data_sources
from corehq.apps.userreports.exceptions import BadBuilderConfigError


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


def has_report_builder_add_on_privilege(request):
    return any(
        has_privilege(request, p) for p in privileges.REPORT_BUILDER_ADD_ON_PRIVS
    )

def has_report_builder_access(request):

    builder_enabled = toggle_enabled(request, toggles.REPORT_BUILDER)
    legacy_builder_priv = has_privilege(request, privileges.REPORT_BUILDER)
    beta_group_enabled = toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)
    has_add_on_priv = has_report_builder_add_on_privilege(request)

    return (builder_enabled and legacy_builder_priv) or beta_group_enabled or has_add_on_priv


def add_event(request, event):
    events = request.session.get(REPORT_BUILDER_EVENTS_KEY, [])
    request.session[REPORT_BUILDER_EVENTS_KEY] = events + [event]


def has_report_builder_trial(request):
    return has_privilege(request, privileges.REPORT_BUILDER_TRIAL)


def can_edit_report(request, report):
    ucr_toggle = toggle_enabled(request, toggles.USER_CONFIGURABLE_REPORTS)
    report_builder_toggle = toggle_enabled(request, toggles.REPORT_BUILDER)
    report_builder_beta_toggle = toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)
    add_on_priv = has_report_builder_add_on_privilege(request)
    created_by_builder = report.spec.report_meta.created_by_builder

    if created_by_builder:
        return report_builder_toggle or report_builder_beta_toggle or add_on_priv
    else:
        return ucr_toggle


def allowed_report_builder_reports(request):
    """
    Return the number of report builder reports allowed
    """
    builder_enabled = toggle_enabled(request, toggles.REPORT_BUILDER)
    legacy_builder_priv = has_privilege(request, privileges.REPORT_BUILDER)
    beta_group_enabled = toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)

    if toggle_enabled(request, toggles.UNLIMITED_REPORT_BUILDER_REPORTS):
        return float("inf")
    if has_privilege(request, privileges.REPORT_BUILDER_30):
        return 30
    if has_privilege(request, privileges.REPORT_BUILDER_15):
        return 15
    if (
        has_privilege(request, privileges.REPORT_BUILDER_TRIAL) or
        has_privilege(request, privileges.REPORT_BUILDER_5) or
        beta_group_enabled or
        (builder_enabled and legacy_builder_priv)
    ):
        return 5


def number_of_report_builder_reports(domain):
    from corehq.apps.userreports.models import ReportConfiguration
    existing_reports = ReportConfiguration.by_domain(domain)
    builder_reports = filter(
        lambda report: report.report_meta.created_by_builder, existing_reports
    )
    return len(builder_reports)


def get_indicator_adapter(config, raise_errors=False):
    from corehq.apps.userreports.sql.adapter import IndicatorSqlAdapter, ErrorRaisingIndicatorSqlAdapter
    from corehq.apps.userreports.es.adapter import IndicatorESAdapter

    if get_backend_id(config) == UCR_ES_BACKEND:
        return IndicatorESAdapter(config)
    else:
        if raise_errors:
            return ErrorRaisingIndicatorSqlAdapter(config)
        return IndicatorSqlAdapter(config)


def get_table_name(domain, table_id):
    def _hash(domain, table_id):
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(domain).hexdigest(), table_id)).hexdigest()[:8]

    return truncate_value(
        'config_report_{}_{}_{}'.format(domain, table_id, _hash(domain, table_id)),
        from_left=False
    )


def is_ucr_table(table_name):
    return table_name.startswith('config_report_')


def truncate_value(value, max_length=63, from_left=True):
    """
    Truncate a value (typically a column name) to a certain number of characters,
    using a hash to ensure uniqueness.
    """
    hash_length = 8
    truncated_length = max_length - hash_length - 1
    if from_left:
        truncated_value = value[-truncated_length:]
    else:
        truncated_value = value[:truncated_length]

    if len(value) > max_length:
        short_hash = hashlib.sha1(value).hexdigest()[:hash_length]
        return '{}_{}'.format(truncated_value, short_hash)
    return value


def get_ucr_es_indices():
    sources = get_all_es_data_sources()
    return [get_table_name(s.domain, s.table_id) for s in sources]


def get_backend_id(config):
    if settings.OVERRIDE_UCR_BACKEND:
        return settings.OVERRIDE_UCR_BACKEND
    return config.backend_id
