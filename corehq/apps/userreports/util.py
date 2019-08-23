from __future__ import absolute_import
from __future__ import unicode_literals
import collections
import hashlib

from corehq import privileges, toggles
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.userreports.adapter import IndicatorAdapterLoadTracker
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY
from django_prbac.utils import has_privilege

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.toggles import ENABLE_UCR_MIRRORS
from corehq.util.couch import DocumentNotFound
from corehq.util.datadog.utils import ucr_load_counter

UCR_TABLE_PREFIX = 'ucr_'
LEGACY_UCR_TABLE_PREFIX = 'config_report_'


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
    if not request.can_access_all_locations:
        return False

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
    return 0


def _get_existing_reports(domain):
    from corehq.apps.userreports.models import ReportConfiguration
    from corehq.apps.userreports.views import TEMP_REPORT_PREFIX
    existing_reports = ReportConfiguration.by_domain(domain)
    return [
        report for report in existing_reports
        if not report.title.startswith(TEMP_REPORT_PREFIX)
    ]


def number_of_report_builder_reports(domain):
    builder_reports = [
        report for report in _get_existing_reports(domain)
        if report.report_meta.created_by_builder
    ]
    return len(builder_reports)


def number_of_ucr_reports(domain):
    ucr_reports = [
        report for report in _get_existing_reports(domain)
        if not report.report_meta.created_by_builder
    ]
    return len(ucr_reports)


def get_indicator_adapter(config, raise_errors=False, load_source="unknown"):
    from corehq.apps.userreports.sql.adapter import IndicatorSqlAdapter, ErrorRaisingIndicatorSqlAdapter, \
        MultiDBSqlAdapter, ErrorRaisingMultiDBAdapter
    requires_mirroring = config.mirrored_engine_ids
    if requires_mirroring and ENABLE_UCR_MIRRORS.enabled(config.domain):
        adapter_cls = ErrorRaisingMultiDBAdapter if raise_errors else MultiDBSqlAdapter
    else:
        adapter_cls = ErrorRaisingIndicatorSqlAdapter if raise_errors else IndicatorSqlAdapter
    adapter = adapter_cls(config)
    track_load = ucr_load_counter(config.engine_id, load_source, config.domain)
    return IndicatorAdapterLoadTracker(adapter, track_load)


def get_table_name(domain, table_id, max_length=50, prefix=UCR_TABLE_PREFIX):
    """
    :param domain:
    :param table_id:
    :param max_length: Max allowable length of table. Default of 50 to prevent long table
                       name issues with CitusDB. PostgreSQL max is 63.
    :param prefix: Table prefix. Configurable to allow migration from old to new prefix.
    :return:
    """
    def _hash(domain, table_id):
        return hashlib.sha1(
            '{}_{}'.format(
                hashlib.sha1(domain.encode('utf-8')).hexdigest(),
                table_id
            ).encode('utf-8')
        ).hexdigest()[:8]

    domain = domain.encode('unicode-escape').decode('utf-8')
    table_id = table_id.encode('unicode-escape').decode('utf-8')
    return truncate_value(
        '{}{}_{}_{}'.format(prefix, domain, table_id, _hash(domain, table_id)),
        max_length=max_length,
        from_left=False
    )


def is_ucr_table(table_name):
    return table_name.startswith(UCR_TABLE_PREFIX)


def truncate_value(value, max_length=63, from_left=True):
    """
    Truncate a value (typically a column name) to a certain number of characters,
    using a hash to ensure uniqueness.
    """
    hash_length = 8
    truncated_length = max_length - hash_length - 1
    value = value.encode('unicode-escape')
    if from_left:
        truncated_value = value[-truncated_length:]
    else:
        truncated_value = value[:truncated_length]

    if len(value) > max_length:
        short_hash = hashlib.sha1(value).hexdigest()[:hash_length]
        return '{}_{}'.format(truncated_value.decode('utf-8'), short_hash)
    return value.decode('utf-8')


def get_ucr_class_name(id):
    """
    This returns the module and class name for a ucr from its id as used in report permissions.
    It takes an id and returns the string that needed for `user.can_view_report(string)`.
    The class name comes from corehq.reports._make_report_class, if something breaks, look there first.
    :param id: the id of the ucr report config
    :return: string class name
    """
    return 'corehq.reports.DynamicReport{}'.format(id)


def get_async_indicator_modify_lock_key(doc_id):
    return 'async_indicator_save-{}'.format(doc_id)


def get_static_report_mapping(from_domain, to_domain):
    from corehq.apps.userreports.models import StaticReportConfiguration, STATIC_PREFIX, \
        CUSTOM_REPORT_PREFIX

    report_map = {}

    for static_report in StaticReportConfiguration.by_domain(from_domain):
        if static_report.get_id.startswith(STATIC_PREFIX):
            report_id = static_report.get_id.replace(
                STATIC_PREFIX + from_domain + '-',
                ''
            )
            is_custom_report = False
        else:
            report_id = static_report.get_id.replace(
                CUSTOM_REPORT_PREFIX + from_domain + '-',
                ''
            )
            is_custom_report = True
        new_id = StaticReportConfiguration.get_doc_id(
            to_domain, report_id, is_custom_report
        )
        # check that new report is in new domain's list of static reports
        try:
            StaticReportConfiguration.by_id(new_id, to_domain)
        except (BadSpecError, DocumentNotFound):
            pass
        else:
            report_map[static_report.get_id] = new_id
    return report_map


def add_tabbed_text(text):
    return '\t' + '\n\t'.join(text.splitlines(False))
