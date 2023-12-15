import collections
import hashlib
import re
from typing import Any, Optional

from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege
from dataclasses import dataclass

from corehq import privileges, toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.linked_domain.util import is_linked_report
from corehq.apps.userreports.adapter import IndicatorAdapterLoadTracker
from corehq.apps.userreports.const import REPORT_BUILDER_EVENTS_KEY, TEMP_REPORT_PREFIX
from corehq.apps.userreports.exceptions import BadSpecError, ReportConfigurationNotFoundError, \
    DataSourceConfigurationNotFoundError
from corehq.toggles import ENABLE_UCR_MIRRORS
from corehq.util import reverse
from corehq.util.couch import DocumentNotFound
from corehq.util.metrics.load_counters import ucr_load_counter
from dimagi.utils.couch.undo import is_deleted, remove_deleted_doc_type_suffix
import logging

UCR_TABLE_PREFIX = 'ucr_'
LEGACY_UCR_TABLE_PREFIX = 'config_report_'


@dataclass
class DataSourceUpdateLog:
    domain: str
    data_source_id: str
    doc_id: str
    rows: Optional[list[dict[str, Any]]] = None

    @property
    def get_id(self):
        return self.doc_id


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
            value.get(lang, None)
            or value.get(default_language(), None)
            or value[sorted(value.keys())[0]]
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
    from corehq.apps.userreports.models import is_data_registry_report
    return (
        _can_edit_report(request, report)
        and not is_linked_report(report)
        and (
            not is_data_registry_report(report)
            or toggles.DATA_REGISTRY_UCR.enabled_for_request(request)
        ))


def can_delete_report(request, report):
    return _can_edit_report(request, report)


def _can_edit_report(request, report):
    if not request.can_access_all_locations:
        return False

    if not request.couch_user.can_edit_reports():
        return False

    ucr_toggle = toggle_enabled(request, toggles.USER_CONFIGURABLE_REPORTS)
    report_builder_toggle = toggle_enabled(request, toggles.REPORT_BUILDER)
    report_builder_beta_toggle = toggle_enabled(request, toggles.REPORT_BUILDER_BETA_GROUP)
    add_on_priv = has_report_builder_add_on_privilege(request)
    created_by_builder = report.report_meta.created_by_builder

    if created_by_builder:
        return report_builder_toggle or report_builder_beta_toggle or add_on_priv
    else:
        return ucr_toggle


def get_referring_apps(domain, report_id):
    to_ret = []
    apps = get_apps_in_domain(domain)
    for app in apps:
        app_url = reverse('view_app', args=[domain, app.id])
        for module in app.get_report_modules():
            module_url = reverse('view_module', args=[domain, app.id, module.unique_id])
            for config in module.report_configs:
                if config.report_id == report_id:
                    to_ret.append({
                        "app_url": app_url,
                        "app_name": app.name,
                        "module_url": module_url,
                        "module_name": module.default_name()
                    })
    return to_ret


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
        has_privilege(request, privileges.REPORT_BUILDER_TRIAL)
        or has_privilege(request, privileges.REPORT_BUILDER_5)
        or beta_group_enabled
        or (builder_enabled and legacy_builder_priv)
    ):
        return 5
    return 0


def get_configurable_and_static_reports(domain):
    from corehq.apps.userreports.models import StaticReportConfiguration
    return get_existing_reports(domain) + StaticReportConfiguration.by_domain(domain)


def get_existing_reports(domain):
    from corehq.apps.userreports.dbaccessors import get_report_and_registry_report_configs_for_domain
    existing_reports = get_report_and_registry_report_configs_for_domain(domain)
    return [
        report for report in existing_reports
        if not (report.title and report.title.startswith(TEMP_REPORT_PREFIX))
    ]


def number_of_report_builder_reports(domain):
    builder_reports = [
        report for report in get_existing_reports(domain)
        if report.report_meta.created_by_builder
    ]
    return len(builder_reports)


def number_of_ucr_reports(domain):
    ucr_reports = [
        report for report in get_existing_reports(domain)
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


def get_report_config_or_not_found(domain, config_id):
    from corehq.apps.userreports.models import ReportConfiguration
    try:
        doc = ReportConfiguration.get_db().get(config_id)
        config = wrap_report_config_by_type(doc)
    except (ResourceNotFound, KeyError, ReportConfigurationNotFoundError):
        raise DocumentNotFound()

    if config.domain != domain:
        raise DocumentNotFound()

    return config


def get_ucr_datasource_config_by_id(indicator_config_id, allow_deleted=False):
    from corehq.apps.userreports.models import (
        id_is_static,
        StaticDataSourceConfiguration,
        DataSourceConfiguration,
    )
    if id_is_static(indicator_config_id):
        return StaticDataSourceConfiguration.by_id(indicator_config_id)
    else:
        doc = DataSourceConfiguration.get_db().get(indicator_config_id)
        return _wrap_data_source_by_doc_type(doc, allow_deleted)


def _wrap_data_source_by_doc_type(doc, allow_deleted=False):
    from corehq.apps.userreports.models import (
        DataSourceConfiguration,
        RegistryDataSourceConfiguration,
    )
    if is_deleted(doc) and not allow_deleted:
        raise DataSourceConfigurationNotFoundError()

    doc_type = remove_deleted_doc_type_suffix(doc["doc_type"])
    return {
        "DataSourceConfiguration": DataSourceConfiguration,
        "RegistryDataSourceConfiguration": RegistryDataSourceConfiguration,
    }[doc_type].wrap(doc)


def wrap_report_config_by_type(config, allow_deleted=False):
    from corehq.apps.userreports.models import (
        ReportConfiguration,
        RegistryReportConfiguration,
    )
    if is_deleted(config) and not allow_deleted:
        raise ReportConfigurationNotFoundError()

    doc_type = remove_deleted_doc_type_suffix(config["doc_type"])
    try:
        return {
            "ReportConfiguration": ReportConfiguration,
            "RegistryReportConfiguration": RegistryReportConfiguration,
        }[doc_type].wrap(config)
    except KeyError:
        raise ReportConfigurationNotFoundError()


def get_domain_for_ucr_table_name(table_name):
    def unescape(value):
        return value.encode('utf-8').decode('unicode-escape')

    pattern = fr"(?:{UCR_TABLE_PREFIX}|{LEGACY_UCR_TABLE_PREFIX})([^_]+)"
    match = re.match(pattern, table_name)
    if match:
        # double-unescape because corehq.apps.userreports.util.get_table_name escapes twice
        return unescape(unescape(match.group(1)))
    raise ValueError(f"Expected {table_name} to start with {UCR_TABLE_PREFIX} or {LEGACY_UCR_TABLE_PREFIX}")


def register_data_source_row_change(domain, data_source_id, doc_ids):
    from corehq.motech.repeaters.models import DataSourceRepeater
    from corehq.motech.repeaters.signals import ucr_data_source_updated
    try:
        if not (
            toggles.SUPERSET_ANALYTICS.enabled(domain)
            and DataSourceRepeater.datasource_is_subscribed_to(domain, data_source_id)
        ):
            return

        for doc_id in doc_ids:
            update_log = DataSourceUpdateLog(
                domain,
                data_source_id=data_source_id,
                doc_id=doc_id,
                # We don't need to set `rows` here. We will determine
                # them at send time. See DataSourceRepeater.payload_doc()
                rows=None,
            )
            ucr_data_source_updated.send_robust(sender=None, update_log=update_log)

    except Exception as e:
        logging.exception(str(e))
