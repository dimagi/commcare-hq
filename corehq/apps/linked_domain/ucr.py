import json
from collections import namedtuple

from django.utils.translation import ugettext as _

from corehq.apps.linked_domain.applications import (
    get_downstream_app_id,
    get_upstream_app_ids,
)
from corehq.apps.linked_domain.const import MODEL_REPORT
from corehq.apps.linked_domain.exceptions import (
    DomainLinkError,
    MultipleDownstreamAppsError,
)
from corehq.apps.linked_domain.models import ReportLinkDetail
from corehq.apps.linked_domain.remote_accessors import \
    get_ucr_config as remote_get_ucr_config
from corehq.apps.userreports.dbaccessors import (
    get_datasources_for_domain,
    get_report_configs_for_domain,
)
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.tasks import rebuild_indicators

LinkedUCRInfo = namedtuple("LinkedUCRInfo", "datasource report")


def create_linked_ucr(domain_link, report_config_id):
    if domain_link.is_remote:
        remote_configs = remote_get_ucr_config(domain_link, report_config_id)
        datasource = remote_configs["datasource"]
        report_config = remote_configs["report"]
    else:
        report_config = ReportConfiguration.get(report_config_id)
        datasource = DataSourceConfiguration.get(report_config.config_id)

    # grab the linked app this linked report references
    downstream_app_id = get_downstream_app_id(domain_link.linked_domain, datasource.meta.build.app_id)
    new_datasource = _get_or_create_datasource_link(domain_link, datasource, downstream_app_id)
    new_report = _get_or_create_report_link(domain_link, report_config, new_datasource)
    return LinkedUCRInfo(datasource=new_datasource, report=new_report)


def get_downstream_report(downstream_domain, upstream_report_id):
    for linked_report in get_report_configs_for_domain(downstream_domain):
        if linked_report.report_meta.master_id == upstream_report_id:
            return linked_report
    return None


def _get_or_create_datasource_link(domain_link, datasource, app_id):
    domain_datsources = get_datasources_for_domain(domain_link.linked_domain)
    existing_linked_datasources = [d for d in domain_datsources if d.meta.master_id == datasource.get_id]
    if existing_linked_datasources:
        return existing_linked_datasources[0]

    datasource_json = datasource.to_json()
    datasource_json["domain"] = domain_link.linked_domain
    datasource_json["_id"] = None
    datasource_json["_rev"] = None

    # app_id is needed to edit reports which is not possible with a linked project due to master_id
    # this is to ensure if the link is removed, the downstream report will be editable
    datasource_json["meta"]["build"]["app_id"] = app_id

    datasource_json["meta"]["master_id"] = datasource.get_id

    _replace_master_app_ids(domain_link.linked_domain, datasource_json)

    new_datasource = DataSourceConfiguration.wrap(datasource_json)
    new_datasource.save()

    rebuild_indicators.delay(new_datasource.get_id, source=f"Datasource link: {new_datasource.get_id}")

    return new_datasource


def _replace_master_app_ids(linked_domain, datasource_json):
    configured_filter = json.dumps(datasource_json['configured_filter'])
    for app_id in get_upstream_app_ids(linked_domain):
        configured_filter = _replace_upstream_app_id(configured_filter, app_id, linked_domain)
    datasource_json['configured_filter'] = json.loads(configured_filter)

    named_filters = json.dumps(datasource_json['named_filters'])
    for app_id in get_upstream_app_ids(linked_domain):
        named_filters = _replace_upstream_app_id(named_filters, app_id, linked_domain)
    datasource_json['named_filters'] = json.loads(named_filters)


def _replace_upstream_app_id(haystack, upstream_app_id, downstream_domain):
    if upstream_app_id in haystack:
        try:
            downstream_app_id = get_downstream_app_id(
                downstream_domain,
                upstream_app_id,
                use_upstream_app_id=False
            )
        except MultipleDownstreamAppsError:
            raise DomainLinkError(_("This report cannot be updated because it references an app "
                                    "that has multiple linked apps."))
        haystack = haystack.replace(upstream_app_id, downstream_app_id)
    return haystack


def _get_or_create_report_link(domain_link, report, datasource):
    existing_linked_reports = get_linked_report_configs(domain_link.linked_domain, report.get_id)
    if existing_linked_reports:
        return existing_linked_reports[0]

    report_json = report.to_json()
    report_json["report_meta"]["master_id"] = report.get_id
    report_json["domain"] = domain_link.linked_domain
    report_json["config_id"] = datasource.get_id
    report_json["_id"] = None
    report_json["_rev"] = None

    new_report = ReportConfiguration.wrap(report_json)
    new_report.save()

    return new_report


def update_linked_ucr(domain_link, report_id, user_id):
    linked_report = ReportConfiguration.get(report_id)
    linked_datasource = linked_report.config

    if domain_link.is_remote:
        remote_configs = remote_get_ucr_config(domain_link, linked_report.report_meta.master_id)
        master_report = remote_configs["report"]
        master_datasource = remote_configs["datasource"]
    else:
        master_report = ReportConfiguration.get(linked_report.report_meta.master_id)
        master_datasource = master_report.config

    _update_linked_datasource(master_datasource, linked_datasource)
    _update_linked_report(master_report, linked_report)

    domain_link.update_last_pull(
        MODEL_REPORT,
        user_id,
        model_detail=ReportLinkDetail(report_id=linked_report.get_id).to_json(),
    )


def _update_linked_datasource(master_datasource, linked_datasource):
    master_datasource_json = master_datasource.to_json()
    linked_datasource_json = linked_datasource.to_json()

    master_datasource_json["domain"] = linked_datasource_json["domain"]
    master_datasource_json["_id"] = linked_datasource_json["_id"]
    master_datasource_json["_rev"] = linked_datasource_json["_rev"]
    master_datasource_json["meta"]["master_id"] = linked_datasource_json["meta"]["master_id"]

    _replace_master_app_ids(linked_datasource_json["domain"], master_datasource_json)

    linked_datasource_json.update(master_datasource_json)
    DataSourceConfiguration.wrap(linked_datasource_json).save()

    rebuild_indicators.delay(linked_datasource.get_id, source=f"Datasource link: {linked_datasource.get_id}")


def _update_linked_report(master_report, linked_report):
    master_report_json = master_report.to_json()
    linked_report_json = linked_report.to_json()

    master_report_json["_id"] = linked_report_json["_id"]
    master_report_json["_rev"] = linked_report_json["_rev"]
    master_report_json["domain"] = linked_report_json["domain"]
    master_report_json["config_id"] = linked_report_json["config_id"]
    master_report_json["report_meta"]["master_id"] = linked_report_json["report_meta"]["master_id"]

    linked_report_json.update(master_report_json)
    ReportConfiguration.wrap(linked_report_json).save()


def get_linked_report_configs(domain, report_id):
    domain_reports = get_report_configs_for_domain(domain)
    existing_linked_reports = [r for r in domain_reports if r.report_meta.master_id == report_id]
    return existing_linked_reports


def get_linked_reports_in_domain(domain):
    reports = get_report_configs_for_domain(domain)
    linked_reports = [report for report in reports if report.report_meta.master_id]
    return linked_reports


def linked_downstream_reports_by_domain(master_domain, report_id):
    """A dict of all downstream domains with and if this is already linked to `report_id`
    """
    from corehq.apps.linked_domain.dbaccessors import get_linked_domains
    linked_domains = {}
    for domain_link in get_linked_domains(master_domain):
        linked_domains[domain_link.linked_domain] = any(
            r for r in get_linked_report_configs(domain_link.linked_domain, report_id)
        )
    return linked_domains


def unlink_reports_in_domain(domain):
    unlinked_reports = []
    reports = get_linked_reports_in_domain(domain)
    for report in reports:
        unlinked_report = unlink_report(report)
        unlinked_reports.append(unlinked_report)

    return unlinked_reports


def unlink_report(report):
    if not report.report_meta.master_id:
        return None

    report.report_meta.master_id = None
    report.save()

    return report
